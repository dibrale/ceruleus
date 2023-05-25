import json

# Load parameter file
with open('params.json', 'r', encoding='utf-8') as f:
    [params, llm_params] = json.load(f)

# Load the character sheet once
with open(params['char_card_path'], 'r', encoding='utf-8') as f:
    attributes = json.load(f)

# Create file paths
path = {
    'judge_template': f"{params['template_dir']}/judge_template.txt",
    'aye_template': f"{params['template_dir']}/aye_template.txt",
    'nay_template': f"{params['template_dir']}/nay_template.txt",
    'body_template': f"{params['template_dir']}/body_template.txt",
    'char_template': f"{params['template_dir']}/character_template.txt",
    'continue_template': f"{params['template_dir']}/continue_template.txt",
    'goal_eval_template': f"{params['template_dir']}/goal_eval_template.txt",
    'goal_thought_eval_template': f"{params['template_dir']}/goal_thought_eval_template.txt",
    'statement_template': f"{params['template_dir']}/statement_template.txt",
    'summarize_template': f"{params['template_dir']}/summarize_template.txt",
    'synthesize_template': f"{params['template_dir']}/synthesize_template.txt",
    'char_card': params['char_card_path'],
    'thoughts': f"{params['work_dir']}/thoughts.json",
    'goals': f"{params['work_dir']}/goals.json",
    'answers': f"{params['work_dir']}/answers.json",
    'thoughts_persistent': f"{params['results_dir']}/thoughts.json",
    'goals_persistent': f"{params['results_dir']}/goals.json",
    'answers_persistent': f"{params['results_dir']}/answers.json",
    'char_log': params['char_log_path'],
    'squire': f"{params['squire_path']}/squire.py",
    'squire_template': f"{params['squire_path']}/template.txt",
    'squire_keyword_template': f"{params['squire_path']}/keyword_template.txt",
    'squire_question': f"{params['squire_path']}/question.txt",
    'squire_model': params['model_path']
}
