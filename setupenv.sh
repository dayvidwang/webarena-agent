# set the URLs in the environment using export
export SHOPPING="http://george.cs.ucsb.edu:7770";
export SHOPPING_ADMIN="http://george.cs.ucsb.edu:7780/admin";
export REDDIT="http://george.cs.ucsb.edu:9999";
export GITLAB="http://george.cs.ucsb.edu:8023";
export MAP="http://ec2-3-131-244-37.us-east-2.compute.amazonaws.com:3000";
export WIKIPEDIA="http://george.cs.ucsb.edu:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing";
# The home page is not currently hosted in the demo site
export HOMEPAGE="PASS"  # set this if HOMEPAGE is hosted later


python browser_env/auto_login.py