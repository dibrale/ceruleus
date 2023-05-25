from modules.config import attributes, params
from modules.logutils import print_v
from modules.tokenutils import llama_token_length

import re


# Check for None and return an empty string in its place. Otherwise, pass the input to output as string.
def assure_string(txt) -> str:
    if not txt:
        return ''
    return str(txt)


# Handle strings and string lists equally, assuring a string as output
def list_or_str_to_str(txt: str | list[str], join_string='\n', if_blank='') -> str:
    if type(txt) is str:
        out = txt.strip()
    elif type(txt) is list[str]:
        out = join_string.join(txt).strip()
    elif not txt:
        return if_blank
    else:
        out = str(txt)
    return out


# Parse a string for boolean output, returning None for inconsistent replies
def bool_from_str(text_in: str, true_str='true', false_str='false', case_sensitive=False) -> bool | None:

    # Apply case sensitivity
    if not case_sensitive:
        text = text_in.lower()
        true = true_str.lower()
        false = false_str.lower()
    else:
        text = text_in
        true = true_str
        false = false_str

    # Check for statements
    is_true = text.count(true)
    is_false = text.count(false)
    if is_true > 0 >= is_false:
        return True
    elif is_false > 0 >= is_true:
        return False
    else:
        return None


# Load JSON answer data up to a maximum token length
async def make_answers_string(answers: dict, tokens_available=800) -> str:
    print_v('Preparing list of previous answers', params['verbose'])
    json_answer_list = answers['answers']
    json_answer_list.reverse()

    answer_text = ''
    for answer in json_answer_list:
        answer_length = llama_token_length(answer)
        tokens_available -= answer_length
        if tokens_available <= 0:
            break
        answer_text = answer + '\n' + answer_text
    answer_text = "\nPrevious Answers:\n" + answer_text
    return answer_text


# Read JSON thought data up to maximum token length
async def make_thoughts_string(thoughts: dict, tokens_available=300) -> str:
    print_v('Preparing thought list', params['verbose'])
    json_thought_list = thoughts['thoughts']
    json_thought_list.reverse()

    thought_text = ''
    for thought in json_thought_list:
        thought_length = llama_token_length(thought)
        tokens_available -= thought_length
        if tokens_available <= 0:
            break
        thought_text = thought + '\n' + thought_text
    thought_text = "\nThoughts:\n" + thought_text
    return thought_text


# Read JSON conversation data up to maximum token length
async def make_convo_string(convo: dict, tokens_available=300) -> str:
    print_v('Preparing conversation data', params['verbose'])
    json_convo_list = convo['data']
    json_convo_list.reverse()

    convo_text = ''
    for line in json_convo_list:
        line_text = ''
        if line[0] and not line[0].strip() == '':
            line_text = f"\n{attributes['your_name']}: {line[0]}"
        if line[1] and not line[1].strip() == '':
            line_text += f"\n{attributes['char_name']}: {line[1]}"
        line_length = llama_token_length(line_text)
        tokens_available -= line_length
        if tokens_available <= 0:
            break
        convo_text = line_text + convo_text
    convo_text = convo_text
    return convo_text


# Get last user statement from a loaded conversation and wrap it in a template for a thought
async def last_statement_thought(convo: dict, template: str) -> str:
    print_v('Getting last statement from user', params['verbose'])
    json_convo_list = convo['data_visible']
    json_convo_list.reverse()

    statement = ''
    for line in json_convo_list:
        if line[0]:
            statement = line[0]
            break

    thought = template.format(user=attributes['your_name'], statement=statement)
    return thought


# Extract question from an arbitrary string
async def parse_question(input_string: str):
    result = re.search(r"Question\s*\d*\s*:\s*\d*\s*(?P<QUESTION>(.*?)[.?])", input_string)

    try:
        question = result.group('QUESTION')
        print_v(f'Question: {question}', params['verbose'])
        return question
    except AttributeError:
        return None


# Test for a string or string list that is not worth processing
def check_nil(query: str | list[str] | dict) -> bool:
    check_list = []

    if type(query) is str:
        check_list = [query]
    elif type(query) is list[str]:
        check_list = query
    elif type(query) is dict:
        intermediate_list = query.values()
        for item in intermediate_list:
            check_list.append(item)

    if not check_list:
        return True

    for item in check_list:
        if not (str(item) == 'Nothing.' or str(item) == ''):
            return False

    return True
