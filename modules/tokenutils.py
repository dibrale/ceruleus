import tiktoken


# Estimate number of tokens remaining given an input string
def llama_token_length(txt, encoding="gpt-3.5-turbo"):
    enc = tiktoken.encoding_for_model(encoding)
    encoded_txt = enc.encode(txt, disallowed_special=set())
    return len(encoded_txt)


# Truncate context for Llama using tiktoken to estimate length
def llama_squeeze(txt, max_tokens=2048, encoding="gpt-3.5-turbo"):
    enc = tiktoken.encoding_for_model(encoding)
    encoded_txt = enc.encode(txt, disallowed_special=set())
    tokens_start = max(0, len(encoded_txt) - max_tokens)
    truncated_encoded_txt = encoded_txt[tokens_start:]
    decoded_txt = enc.decode(truncated_encoded_txt)
    return decoded_txt


# Estimate number of tokens remaining given an input string
def llama_remaining_tokens(txt, max_tokens=2048, encoding="gpt-3.5-turbo"):
    remaining_length = max_tokens - llama_token_length(txt, encoding=encoding)
    return remaining_length


# Return text in llama-parsable chunks
def llama_chunk(txt, step_tokens=1024, encoding="gpt-3.5-turbo") -> list[str]:
    enc = tiktoken.encoding_for_model(encoding)
    encoded_txt = enc.encode(txt, disallowed_special=set())
    out_list = []
    for i in range(0, len(encoded_txt)-1, step_tokens):
        last_index = min(i+step_tokens, len(encoded_txt))-1
        chunk = enc.decode(encoded_txt[i:last_index])
        out_list.append(chunk)
    return out_list

