import json

# Load parameter file
with open('params.json', 'r', encoding='utf-8') as f:
    params = json.load(f)

# Load the character sheet once
with open(params['char_card_path'], 'r', encoding='utf-8') as f:
    attributes = json.load(f)
