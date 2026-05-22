import os
import re
import math

def scale_value(match):
    val = int(match.group(1))
    # Scale fonts by 1.3
    new_val = math.ceil(val * 1.3)
    return f"{match.group(0).split(':')[0]}: {new_val}px"

def scale_width(match):
    val = int(match.group(1))
    new_val = math.ceil(val * 1.25)
    return f"{match.group(0).split(':')[0]}: {new_val}px"

for root, dirs, files in os.walk("src/components"):
    for file in files:
        if file.endswith(".css"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()
            
            # Scale font-size
            content = re.sub(r'font-size:\s*(\d+)px', scale_value, content)
            # Scale width
            content = re.sub(r'(?<!border-)width:\s*(\d+)px', scale_width, content)
            # Scale max-width
            content = re.sub(r'max-width:\s*(\d+)px', scale_width, content)
            # Scale height
            content = re.sub(r'(?<!line-)height:\s*(\d+)px', scale_width, content)
            
            with open(path, "w") as f:
                f.write(content)
print("Scaling done!")
