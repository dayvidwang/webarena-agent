import os
from bs4 import BeautifulSoup
import webbrowser
import json

class SingleActionTrace:
    def __init__(self, observation, url, prev_action, raw_prediction, action, parsed_action, img):
        self.observation = observation
        self.url = url
        self.prev_action = prev_action
        self.raw_prediction = raw_prediction
        self.action = action
        self.parsed_action = parsed_action
        self.img = img

    def __str__(self):
        return f"Observation: {self.observation}\nURL: {self.url}\nPrev Action: {self.prev_action}\nRaw Prediction: {self.raw_prediction}\nAction: {self.action}\nParsed Action: {self.parsed_action}"


    def to_html(self):
        html_content = f"""<html>
        <head>
            <style>pre {{ white-space: pre-wrap; word-wrap: break-word; }}</style>
        </head>
            <body>
                {self.url}
                {self.img}
                {self.observation}
                {self.prev_action}
                {self.raw_prediction}
                {self.action}
                {self.parsed_action}
            </body>
        </html>"""

        return html_content
    
    def open_html(self):
        with open("temp.html", "w") as f:
            f.write(self.to_html())
        temp_html_path = os.path.abspath("temp.html")
        webbrowser.open(f"file://{temp_html_path}")

def separate_traces(filepath) -> list[SingleActionTrace]:
    with open(filepath, "r") as f:
        content = f.read()
        soup = BeautifulSoup(content, 'html.parser')

        # reformat back into their original html tags
        flattened_observations = [f"<pre>{div.find('pre').text}</pre>" for div in soup.find_all("div", {"class": "state_obv"})]
        flattened_images = [f"<img src={img['src']}>" for img in soup.find_all("img")]
        flattened_urls = [url for url in soup.find_all("h3", {"class": "url"})]
        flattened_prev_actions = [f"<div>{action.text}</div>" for action in soup.find_all("div", {"class": "prev_action"})]
        flattened_raw_predictions = [f"<div>{prediction.text}</div>" for prediction in soup.find_all("div", {"class": "raw_parsed_prediction"})]
        flattened_actions = [f"<div>{action.text}</div>" for action in soup.find_all("div", {"class": "action_object"})]
        flattened_parsed_actions = [f"<div>{action.text}</div>" for action in soup.find_all("div", {"class": "parsed_action"})]

        # get the formatted traces
        flattened_traces = []
        for observation, url, prev_action, raw_prediction, action, parsed_action, img in zip(flattened_observations, flattened_urls, flattened_prev_actions, flattened_raw_predictions, flattened_actions, flattened_parsed_actions, flattened_images):
            trace = SingleActionTrace(observation, url, prev_action, raw_prediction, action, parsed_action, img)
            flattened_traces.append(trace)

        return flattened_traces

def generate_single_trace():
    folder = "919_gpt4_8k_cot"
    result_folder = "experiments/annotate_traces/single_traces"
    for file in os.listdir(folder):
        if file.endswith(".html"):
            filepath = os.path.join(folder, file)
            traces = separate_traces(filepath)
            # get filename without html using os path
            filename = os.path.splitext(os.path.basename(filepath))[0]
            # create a folder for each trace
            trace_folder = os.path.join(result_folder, filename)
            os.makedirs(trace_folder, exist_ok=True)
            for i, trace in enumerate(traces):
                with open(os.path.join(trace_folder, f"{filename}_{i}.html"), "w") as f:
                    f.write(trace.to_html())

def annotate_traces():
    # open each trace in browser. for each, ask for either right or wrong
    folder = "experiments/annotate_traces/single_traces"
    result_file = "experiments/annotate_traces/annotations.json"
    if os.path.exists(result_file):
        with open(result_file, "r") as f:
            annotations = json.load(f)
    else:
        annotations = {}
    for trace_folder in os.listdir(folder):
        trace_folder = os.path.join(folder, trace_folder)
        for trace_file in os.listdir(trace_folder):
            single_trace_name = os.path.splitext(os.path.basename(trace_file))[0]
            if single_trace_name in annotations:
                continue
            trace_file = os.path.join(trace_folder, trace_file)
            webbrowser.open(f"file://{os.path.abspath(trace_file)}")
            annotation = input("Is this trace correct? (y/n/skip)")
            while annotation != "y" and annotation != "n" and annotation != "skip":
                annotation = input("Please enter either 'y' or 'n' or 'skip'")
            if annotation == "y":
                annotations[single_trace_name] = True
            elif annotation == "n":
                annotations[single_trace_name] = False
            elif annotation == "skip":
                annotations[single_trace_name] = "skip"
            with open(result_file, "w") as f:
                json.dump(annotations, f)
            


def main():
    annotate_traces()


        

if __name__ == "__main__":
    main()
