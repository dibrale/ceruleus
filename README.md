# Ceruleus

Use [Squire](https://github.com/dibrale/squire) to give a local LLM running in oobabooga's [text-generation-webui](https://github.com/oobabooga/text-generation-webui) the ability to look up information online and generate messages autonomously on the basis of this information.

## Philosophy

The ultimate goal of Ceruleus is to organize information transfer between modules that provide a back-end 'internal monologue' for chat agents. This would enable chat agents to take the initiative in posting chat messages rather than relying exclusively on new user input to trigger a response. To facilitate this ultimate aim, the script uses asynchronous routines where possible. This carries the welcome benefit of fast exchange, making execution times mostly dependent on total LLM inference speed.

# Software Requirements

- A working installation of [text-generation-webui](https://github.com/oobabooga/text-generation-webui)
- Local LLM weights in ggml format

## Installation

1. Clone this repository and navigate into its directory.
2. Install dependencies, i.e. using `pip install -r requirements.txt`.
3. Clone [Squire](https://github.com/dibrale/squire), i.e. using `git clone https://github.com/dibrale/squire.git`.
4. Navigate to `squire/` and install Squire dependencies, i.e. using `pip install -r requirements.txt` once again.
5. Open `params.json` in the root directory of Ceruleus and edit the parameters to suit your machine. These are detailed below.
6. Back up your character chat log, i.e. `text-generation-webui/logs/<character_name>_persistent.json`. Ceruleus edits the chat log directly when it runs.
7. From the Ceruleus root directory, you can now run `python main.py` to initialize the script.

## Parameters and Usage

Edit the params.json file before running Ceruleus to reflect your setup, with particular attention to `CUDA_VISIBLE_DEVICES`, `char_card_path`, `char_log_path` and `squire_model_path`. The full list of parameters is described below.

| Parameter | Type | Default | Description |
| ------------- | ------------- | ------------- | ------------- |
| script_name | String | ceruleus | The name of the script as it appears on every line of terminal output. |
| verbose | Boolean | false | Set to enable additional terminal output for debugging. |
| CUDA_VISIBLE_DEVICES | String | 0 | Comma-separated list of all CUDA devices that should be visible to Ceruleus (eg. use '0,1' if you have two GPUs and want both to be detectable). Passes the shell variable of the same name on execution of external scripts. | 
| results_dir | String | results | Path to results directory. |
| work_dir | String | results | Path to work directory. |
| template_dir | String | templates | Path to templates directory. |
| char_card_path | String | char.json | Path to the character file Ceruleus is to use, eg. `text_generation_webui/characters/<character_name>.json` |
| char_log_path | String | char_persistent.json | Path to the conversation log file Ceruleus is to use, eg. `text_generation_webui/logs/<character_name>_persistent.json` |
| squire_path | String | squire | Path to the directory where `squire.py` is located. |
| squire_out_dir | String | squire_output | Path to the directory where Squire will write its output. This directory will be monitored for text file activity, and any text file altered within that directory will be processed as an answer string |
| model_path | String | ggml-model-q5_1.bin | Path to the model weights to be used when running Squire. Only CPU inference with [llama.cpp](https://github.com/ggerganov/llama.cpp) is supported at this time, so this should be a \*.bin file. |
| telesend | Boolean | false | Set to write goals in `data_visible` of the persistent conversation log instead of just in `data`. |
| retry_delay | Integer | 10 | Retry delay for web UI API calls |
| answer_attempts_max | Integer | 3 | Maximum number of times to run Squire on the same question before reappraisal |

Included in this parameter file is another object containing parameters used by the appraisal code LLM. These are described in detail elsewhere.

| Parameter | Type | Default |
| ------------- | ------------- | ------------- |
| n_ctx | Integer | 1800 |
| top_p | Float | 0.8 |
| top_k | Integer | 30 |
| repeat_penalty | Float | 1.1 |
| temperature | Float | 0.4 |
| n_batch | Integer | 700 |
| n_threads | Integer | 8 |

Additional Llama parameters that can be passed by LangChain to llama.cpp can be included in this object.

## Operation
This software is a work in progress, so a number of convenience features are absent at the time of this writing.

![Entity flow diagram of the main loop](https://github.com/dibrale/ceruleus/blob/main/ceruleus_plan.drawio.svg)

Note that this main loop diagram does not yet include appraisal code and associated flow control.

### Precautions

- Back up your character chat log, i.e. the file ending with `_persistent.json`, if this file is important to you! Ceruleus writes directly to this log. While Ceruleus is not expected to corrupt or delete the chat log, it is good to have a backup in case of unwanted or excessive output.
- While Ceruleus runs recursively and automatically, it is reccommended to supervize the script from time to time while it is running. Errors generated by Squire or the text-generation-webui API may stop the main loop of Ceruleus from running. If this happens, stop Ceruleus and start it again.
- Attempting to chat with the agent via the web UI while Ceruleus is running is presently not reccommended. Stop Ceruleus and reload the character before resuming your conversation.

### Instructions

- **Initializing:** Run `python main.py` from the root directory of the script.
- **Beginning execution:** Navigate to the root directory of Ceruleus in a separate terminal instance, and type `touch squire_output/out.txt`. Alternatively, overwrite squire_output_out.txt with a file containing an initial answer message of your choice (e.g.: "No answers yet. Ask a question in your reply.")
- **Stopping the script:** Ceruleus runs as a typical asynchronous Python script, but has no user interface or defined stop condition. Stop Ceruleus with 'control-C' once it has generated the desirable amount of output in your chat agent's persistent log. 
- **Checking the chat log:** You can check the log by reloading the caracter periodically in text-generation-webui - the chat does not auto-update. 
- **Using intermediate results:** The \*.json files in 'results/' can be interrogated at any time for use in downstream applications such as summarization and separate LLM-powered goal-setting.

## Afterword

While Ceruleus is a work in progress, I hope you find this tool both useful and simple to use. Please let me know if you encounter any issues or have any suggestions.




