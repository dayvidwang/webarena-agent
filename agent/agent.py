import argparse
import json
from typing import Any, Optional

import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox

import tiktoken
from beartype import beartype

from agent.prompts import *
from browser_env import Trajectory
from browser_env.actions import (
    Action,
    ActionParsingError,
    create_id_based_action,
    create_none_action,
    create_playwright_action,
)
from browser_env.utils import Observation, StateInfo
from llms import (
    call_llm,
    generate_from_huggingface_completion,
    generate_from_openai_chat_completion,
    generate_from_openai_completion,
    lm_config,
)
from llms.tokenizers import Tokenizer


class Agent:
    """Base class for the agent"""

    def __init__(self, *args: Any) -> None:
        pass

    def next_action(
        self, trajectory: Trajectory, intent: str, meta_data: Any
    ) -> Action:
        """Predict the next action given the observation"""
        raise NotImplementedError

    def reset(
        self,
        test_config_file: str,
    ) -> None:
        raise NotImplementedError


class TeacherForcingAgent(Agent):
    """Agent that follows a pre-defined action sequence"""

    def __init__(self) -> None:
        super().__init__()

    def set_action_set_tag(self, tag: str) -> None:
        self.action_set_tag = tag

    def set_actions(self, action_seq: str | list[str]) -> None:
        if isinstance(action_seq, str):
            action_strs = action_seq.strip().split("\n")
        else:
            action_strs = action_seq
        action_strs = [a.strip() for a in action_strs]

        actions = []
        for a_str in action_strs:
            try:
                if self.action_set_tag == "playwright":
                    cur_action = create_playwright_action(a_str)
                elif self.action_set_tag == "id_accessibility_tree":
                    cur_action = create_id_based_action(a_str)
                else:
                    raise ValueError(
                        f"Unknown action type {self.action_set_tag}"
                    )
            except ActionParsingError as e:
                cur_action = create_none_action()

            cur_action["raw_prediction"] = a_str
            actions.append(cur_action)

        self.actions: list[Action] = actions

    def next_action(
        self, trajectory: Trajectory, intent: str, meta_data: Any
    ) -> Action:
        """Predict the next action given the observation"""
        return self.actions.pop(0)

    def reset(
        self,
        test_config_file: str,
    ) -> None:
        with open(test_config_file) as f:
            ref_actions = json.load(f)["reference_action_sequence"]
            tag = ref_actions["action_set_tag"]
            action_seq = ref_actions["action_sequence"]
            self.set_action_set_tag(tag)
            self.set_actions(action_seq)


class PromptAgent(Agent):
    """prompt-based agent that emits action given the history"""

    @beartype
    def __init__(
        self,
        action_set_tag: str,
        lm_config: lm_config.LMConfig,
        prompt_constructor: PromptConstructor,
    ) -> None:
        super().__init__()
        self.lm_config = lm_config
        self.prompt_constructor = prompt_constructor
        self.action_set_tag = action_set_tag

    def set_action_set_tag(self, tag: str) -> None:
        self.action_set_tag = tag

    @beartype
    def next_action(
        self, trajectory: Trajectory, intent: str, meta_data: dict[str, Any]
    ) -> Action:
        prompt = self.prompt_constructor.construct(
            trajectory, intent, meta_data
        )
        lm_config = self.lm_config
        n = 0
        while True:
            response = call_llm(lm_config, prompt)
            force_prefix = self.prompt_constructor.instruction[
                "meta_data"
            ].get("force_prefix", "")
            response = f"{force_prefix}{response}"
            print(f"response: {response}")
            n += 1
            try:
                parsed_response = self.prompt_constructor.extract_action(
                    response
                )
                if self.action_set_tag == "id_accessibility_tree":
                    action = create_id_based_action(parsed_response)
                elif self.action_set_tag == "playwright":
                    action = create_playwright_action(parsed_response)
                else:
                    raise ValueError(
                        f"Unknown action type {self.action_set_tag}"
                    )
                action["raw_prediction"] = response
                break
            except ActionParsingError as e:
                if n >= lm_config.gen_config["max_retry"]:
                    action = create_none_action()
                    action["raw_prediction"] = response
                    break

        return action

    def reset(self, test_config_file: str) -> None:
        pass

class UserGuidedAgent(Agent):
    """prompt based agent that takes user input at each timestep and emits action given the history in the same form as PromptAgent"""
    @beartype
    def __init__(
        self,
        action_set_tag: str,
        lm_config: lm_config.LMConfig,
        prompt_constructor: PromptConstructor,
    ) -> None:
        super().__init__()
        self.lm_config = lm_config
        self.prompt_constructor = prompt_constructor
        self.action_set_tag = action_set_tag
        self.default_agent= PromptAgent(action_set_tag, lm_config, prompt_constructor)

    def set_action_set_tag(self, tag: str) -> None:
        self.action_set_tag = tag

    class CustomDialog(simpledialog.Dialog):
        def __init__(self, master, task_instruction, initial_value=""):
            self.task_instruction = task_instruction
            self.initial_value = initial_value
            super().__init__(master)

        def body(self, master):
            self.title("Input Instructions")
            
            # Display original task instruction
            task_label = tk.Label(master, text=f"Task: {self.task_instruction}", font=("Arial", 12, "bold"))
            task_label.pack(pady=(10, 5))

            # Display input instructions as a label
            tk.Label(master, text="Please enter your instructions below:\n(Include all necessary details)").pack()

            # Create a larger text box
            self.text_box = tk.Text(master, width=40, height=10)
            self.text_box.pack(padx=10, pady=10)

            if self.initial_value:
                self.text_box.insert("1.0", self.initial_value)

            return self.text_box  # initial focus on the text box

        def apply(self):
            self.result = self.text_box.get("1.0", "end-1c")  # get content from text box, strip last newline

    def get_instruction(self, task_instruction):
        root = tk.Tk()
        root.withdraw()  # hide the main window
        d = self.CustomDialog(root, task_instruction)
        instruction = d.result
        root.destroy()
        return instruction.rstrip() if instruction else None


    def open_response_window(self,response) -> Optional[str]:
        """ Open a new window for the user to edit and confirm or deny the response. """
        root = tk.Tk()
        root.withdraw()
        d = self.CustomDialog(root, "modify the response as needed", response)
        edited_response = d.result
        root.destroy()
        return edited_response.rstrip() if edited_response else None

    @beartype
    def next_action(
        self, trajectory: Trajectory, intent: str, meta_data: dict[str, Any], confirm: bool = True
    ) -> Action:
        lm_config = self.lm_config
        n = 0
        #?: Can we just concatenate the user input to the intent? e.g. intent...The next step should be xyz because xyz.
        # if user_input is None, just continue with default operation
        while True:
            # allow user to select between viewing state or providing next action
            state_info: StateInfo = trajectory[-1]  # type: ignore[assignment]

            obs = state_info["observation"][self.prompt_constructor.obs_modality]
            with open("current_state.txt", "w") as f:
                f.write(str(obs))
            user_input: str = self.get_instruction(intent)
            meta_data['guidance'] = user_input

            prompt = self.prompt_constructor.construct(
                trajectory, intent, meta_data
            )
            while True:
                response = call_llm(lm_config, prompt)
                force_prefix = self.prompt_constructor.instruction[
                    "meta_data"
                ].get("force_prefix", "")
                response = f"{force_prefix}{response}"
                n += 1
                try:
                    parsed_response = self.prompt_constructor.extract_action(
                        response
                    )
                    if self.action_set_tag == "id_accessibility_tree":
                        action = create_id_based_action(parsed_response)
                    elif self.action_set_tag == "playwright":
                        action = create_playwright_action(parsed_response)
                    else:
                        raise ValueError(
                            f"Unknown action type {self.action_set_tag}"
                        )
                    action["raw_prediction"] = response
                    # action["guidance"] = user_input
                    break
                except ActionParsingError as e:
                    if n >= lm_config.gen_config["max_retry"]:
                        action = create_none_action()
                        action["raw_prediction"] = response
                        # action["guidance"] = user_input
                        break


            if confirm:
                confirm_action = self.open_response_window(response)
                if confirm_action is not None:
                    try:
                        parsed_response = self.prompt_constructor.extract_action(
                            confirm_action
                        )
                        if self.action_set_tag == "id_accessibility_tree":
                            action = create_id_based_action(parsed_response)
                        elif self.action_set_tag == "playwright":
                            action = create_playwright_action(parsed_response)
                        else:
                            raise ValueError(
                                f"Unknown action type {self.action_set_tag}"
                            )
                        action["raw_prediction"] = confirm_action
                        # action["guidance"] = user_input
                        break
                    except ActionParsingError as e:
                        print(f"Invalid action, please try again. {e}")
                        continue
            else:
                break

        return action 
    
    def reset(self, test_config_file: str) -> None:
        pass

class UiPromptAgent(Agent):
    """prompt-based agent that emits action given the history also has a running UI to allow users to confirm or modify the response."""

    @beartype
    def __init__(
        self,
        action_set_tag: str,
        lm_config: lm_config.LMConfig,
        prompt_constructor: PromptConstructor,
    ) -> None:
        super().__init__()
        self.lm_config = lm_config
        self.prompt_constructor = prompt_constructor
        self.action_set_tag = action_set_tag

    def set_action_set_tag(self, tag: str) -> None:
        self.action_set_tag = tag

    @beartype
    def next_action(
        self, trajectory: Trajectory, intent: str, meta_data: dict[str, Any]
    ) -> Action:
        prompt = self.prompt_constructor.construct(
            trajectory, intent, meta_data
        )
        lm_config = self.lm_config
        n = 0
        while True:
            response = call_llm(lm_config, prompt)
            force_prefix = self.prompt_constructor.instruction[
                "meta_data"
            ].get("force_prefix", "")
            response = f"{force_prefix}{response}"
            print(f"response: {response}")
            n += 1
            try:
                parsed_response = self.prompt_constructor.extract_action(
                    response
                )
                if self.action_set_tag == "id_accessibility_tree":
                    action = create_id_based_action(parsed_response)
                elif self.action_set_tag == "playwright":
                    action = create_playwright_action(parsed_response)
                else:
                    raise ValueError(
                        f"Unknown action type {self.action_set_tag}"
                    )
                action["raw_prediction"] = response
                break
            except ActionParsingError as e:
                if n >= lm_config.gen_config["max_retry"]:
                    action = create_none_action()
                    action["raw_prediction"] = response
                    break

        return action

    def reset(self, test_config_file: str) -> None:
        pass

def construct_agent(args: argparse.Namespace) -> Agent:
    llm_config = lm_config.construct_llm_config(args)
    agent: Agent
    if args.agent_type == "teacher_forcing":
        agent = TeacherForcingAgent()
    elif args.agent_type == "prompt" or args.agent_type == "guided":
        with open(args.instruction_path) as f:
            constructor_type = json.load(f)["meta_data"]["prompt_constructor"]
        tokenizer = Tokenizer(args.provider, args.model)
        prompt_constructor = eval(constructor_type)(
            args.instruction_path, lm_config=llm_config, tokenizer=tokenizer
        )
        if args.agent_type == "prompt":

            agent = PromptAgent(
                action_set_tag=args.action_set_tag,
                lm_config=llm_config,
                prompt_constructor=prompt_constructor,
            )
        elif args.agent_type == "guided":
            agent = UserGuidedAgent(
                action_set_tag=args.action_set_tag,
                lm_config=llm_config,
                prompt_constructor=prompt_constructor,
            )
        elif args.agent_type == "ui":
            agent = UiPromptAgent(

            )
    else:
        raise NotImplementedError(
            f"agent type {args.agent_type} not implemented"
        )
    return agent


