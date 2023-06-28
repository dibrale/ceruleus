# Ceruleus

Let chat agents set their own goals and take initiative in conversation. 


## Description

Ceruleus provides a back-end 'internal monologue' for chat agents by implementing flexible loops of goal setting, question formulation, information retrieval and appraisal with natural points for optional user intervention. Information retrieval and summarization is implemented using [Squire](https://github.com/dibrale/squire), while the primary user interaction occurs via oobabooga's [text-generation-webui](https://github.com/oobabooga/text-generation-webui).The API of the latter is also used for high level decision-making by the agent.

Moving beyond the traditional prompt and response interaction model, chat agents running Ceruleus take initiative in conversation, looking up information online and generating relevant messages autonomously on the basis of this information. Ceruleus makes this possible by prompting the language model for optional speech after the completion of an information analysis loop. In addition, information gathered by an agent in the course of its internal process - as well as the history of its successes and failures - is available to it via the 'data' object of the text-generation-webui chat log. 

Additional data buffers for answers, goals and thoughts are used for internal processing by the agent, representing a 'subconscious' layer of memory that is not directly accessible by the LLM responsible for generating speech. The speech itself is produced in conjunction with goal-setting and question-asking in order to ensure good semantic coupling between the agent's speech and intent. However, portions of the Ceruleus loop also give the chat agent an opportunity to set goals and pose new questions intrinsically, without access to the conversation log.

Given the limitations of openly available LLMs and the amount of additional processing performed by the agent in conjunction with the generation of speech, autonomous speech output is carefully groomed within Ceruleus by the sequential application of regular expressions. While the modular code structure of Ceruleus allows arbitrary LLM-powered steps to be easily introduced in order to further improve output quality, adjusting the behavior of a chat agent running Ceruleus requires little to no knowledge of coding.

The Ceruleus back-end can be monitored live and easily interrogated using a GUI. This graphical interface includes a suite of tools providing insight into the 'thought process' of the agent. It also allows for easy process monitoring and control, as well as the export of data for offline analysis. The Ceruleus GUI also offers easy access to all the prompt templates used by the back-end for LLM-powered steps, enabling real-time prompt engineering.


## Design Notes

- The Ceruleus back-end uses asynchronous routines where possible. This carries the welcome benefit of fast exchange, making execution times mostly dependent on total LLM inference speed. It also enables live, non-blocking control of the back-end via the GUI.


- The project code is kept as modular as possible, enabling the reuse of standard small utility functions. This also permits the easy addition of arbitrary LLM-powered steps via the `process()` function to any point in the code. By default, this function will summarize text. In conjunction with a custom text file in 'templates', it can do everything else. 


- While the Ceruleus GUI is intended to run on the same local machine as the back-end, it uses a websockets interface that in principle allows the client to control the back-end and receive process updates remotely. Remote file management, touch-off and log reading are not yet supported.


- Squire is presently an unreliable solution for information retrieval, as the local LLMs powering it have trouble parsing what they retrieve and are prone to confabulation (i.e. hallucination). However, it functions well as a source of extrinsic input to fuel the internal process of an agent running Ceruleus. The information retrieval 'effector' step is particularly well-insulated from the rest of the code, making Squire relatively easy to replace if desired.


- The intended setup for running Ceruleus is a machine that runs one LLM on GPU via text-generation-webui for context-heavy inference in addition to 'co-processing' LLMs operating via CPU inference. One is launched by Ceruleus for context-light internal steps, and Squire launches another one.


- The asynchronous nature of the back-end can in principle allow for extensive parallelization. This has been difficult to try out in practice due to hardware limitations. However, it is presently possible for a user to converse with the forward-facing webui LLM while the co-processing models are otherwise engaged.

# Software Requirements

- Python 3.10
- A working installation of [text-generation-webui](https://github.com/oobabooga/text-generation-webui)
- Local LLM weights in ggml format

## Installation

**1.** Clone this repository and navigate into its directory. i.e.: 
    ```
    git clone https://github.com/dibrale/ceruleus.git
    cd ceruleus
    ```
**2.** Install dependencies, i.e. using 
   ```
   pip install -r requirements.txt
   ```
**3.** Clone [Squire](https://github.com/dibrale/squire), i.e. using 

   ```
   git clone https://github.com/dibrale/squire.git
   ```
**4.** Install Squire dependencies, i.e. using 

    ```
    pip install -r squire/requirements.txt
    ```
**5.** Back up your character chat log, i.e. 

    ```
    mkdir backups
    cp text-generation-webui/logs/<character_name>_persistent.json backups/<character_name>_persistent.json.bak
    ```
    Ceruleus edits the chat log directly when it runs.

<hr>

**Note:** The GUI starts immediately after the server using the current `start.sh` script, so parameter changes made via the GUI will not be reflected until the next run.

<hr>

**6.** Open `params.json` in the root directory of Ceruleus and edit the parameters to suit your machine. These are detailed below.

**7.** Start Ceruleus using the provided script, i.e.
   ```
   ./start.sh
   ```
   This will start the Ceruleus server in the background with output directed to `logfile.log`, then start the GUI in the foreground. To stop the back-end, make note of the process ID in the output and `kill -9` that process.

## Parameters and Usage

Edit the `params.json` file before running Ceruleus to reflect your setup, with particular attention to `CUDA_VISIBLE_DEVICES`, `char_card_path`, `char_log_path` and `squire_model_path`. The full list of parameters is described below.

| Parameter            | Type    | Default              | Description                                                                                                                                                                                                                   |
|----------------------|---------|----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| script_name          | String  | ceruleus             | The name of the script as it appears on every line of terminal output.                                                                                                                                                        |
| host                 | String  | localhost            | Preferred name of the local host. This may need to be changed to '127.0.0.1' on some machines, or to other addresses in the case of exotic setups                                                                             |
| port                 | Integer | 1230                 | Port on which to run the server API                                                                                                                                                                                           |
| verbose              | Boolean | false                | Set to enable additional terminal output for debugging.                                                                                                                                                                       |
| CUDA_VISIBLE_DEVICES | String  | 0                    | Comma-separated list of all CUDA devices that should be visible to Ceruleus (eg. use '0,1' if you have two GPUs and want both to be detectable). Passes the shell variable of the same name on execution of external scripts. | 
| results_dir          | String  | results              | Path to results directory.                                                                                                                                                                                                    |
| work_dir             | String  | results              | Path to work directory.                                                                                                                                                                                                       |
| template_dir         | String  | templates            | Path to templates directory.                                                                                                                                                                                                  |
| char_card_path       | String  | char.json            | Path to the character file Ceruleus is to use, eg. `text_generation_webui/characters/<character_name>.json`                                                                                                                   |
| char_log_path        | String  | char_persistent.json | Path to the conversation log file Ceruleus is to use, eg. `text_generation_webui/logs/<character_name>_persistent.json`                                                                                                       |
| squire_path          | String  | squire               | Path to the directory where `squire.py` is located.                                                                                                                                                                           |
| squire_out_dir       | String  | squire_output        | Path to the directory where Squire will write its output. This directory will be monitored for text file activity, and any text file altered within that directory will be processed as an answer string                      |
| model_path           | String  | ggml-model-q5_1.bin  | Path to the model weights to be used when running Squire. Only CPU inference with [llama.cpp](https://github.com/ggerganov/llama.cpp) is supported at this time, so this should be a \*.bin file.                             |
| telesend             | Boolean | false                | Set to write goals in `data_visible` of the persistent conversation log instead of just in `data`.                                                                                                                            |
| retry_delay          | Integer | 10                   | Retry delay for web UI API calls, in seconds                                                                                                                                                                                  |
| ping_interval        | Integer | 15                   | Ping interval for websockets, in seconds                                                                                                                                                                                      |
| ping_timeout         | Integer | 60                   | Ping timeout for websockets, in seconds                                                                                                                                                                                       |
| answer_attempts_max  | Integer | 2                    | Maximum number of times to run Squire on the same question before reappraisal                                                                                                                                                 |

Included in this parameter file is another object containing parameters used by the appraisal code LLM. These are described in detail elsewhere.

| Parameter | Type | Default |
| ------------- | ------------- |---------|
| n_ctx | Integer | 1800    |
| top_p | Float | 0.8     |
| top_k | Integer | 30      |
| repeat_penalty | Float | 1.1     |
| temperature | Float | 0.4     |
| n_batch | Integer | 700     |
| n_threads | Integer | 8       |
| n_gpu_layers | Integer | 10      |

Additional Llama parameters that can be passed by LangChain to llama.cpp can be included in this object. The final object in the parameter file contains all the parameters that can be passed to [text-generation-webui](https://github.com/oobabooga/text-generation-webui). See the repository of that project for details regarding these.

## Operation
<hr>

**Note:** A number of convenience features are absent from the open version of Ceruleus at the time of this writing. Contact [ADMC Science and Consulting](mailto:alexander@admedicalcorp.com) via email if you are interested in the priority implementation of features that suit your needs.
<hr>


### Precautions

- Back up your character chat log, i.e. the file ending with `_persistent.json`, if this file is important to you! Ceruleus writes directly to this log. While Ceruleus is not expected to corrupt or delete the chat log, it is good to have a backup in case of unwanted or excessive output.
- While Ceruleus runs recursively and automatically, it is recommended to supervise the script from time to time while it is running. 
- Errors generated by Squire or the text-generation-webui API may stop the main loop of Ceruleus from running. If this happens, try pressing 'touch' to restart the Ceruleus loop. If this does not work, stop Ceruleus and start it again.
- The text-generation-webui does not presently support request queuing, so calling its API while the program is busy will error out the webui. When you wish to use the webui in order to talk to the agent, ensure that Ceruleus is not engaging the webui by checking the bottom status bar or 'Status' tab. Then, pause Ceruleus using the general pause or webui pause toggle in the controls before writing to the agent. When your exchange is completed, reset the toggles.

### GUI Instructions

The Ceruleus GUI was written using [PySimpleGUI](https://github.com/PySimpleGUI/PySimpleGUI). It opens with `start.sh`, but can be opened on its own with `python ceruleus_client.py`. This can be useful for parameter editing before starting the software. Once open, the GUI will display a status bar and five tabs: Parameters, Controls, Status, Log and Results.
<hr>

#### Parameters Tab

From the parameters tab, you can view, modify, delete and save parameters for the back-end.

![params.png](ceruleus_client_pics%2Fparams.png)

- Click 'Browse' to find your parameter file, then click 'Load'. A green 'V' will appear if the operation was successful.
- To modify or delete a parameter, click on any of the items in the three lists. The 'Edit Parameter' frame will automatically populate with the details of the item. 
- Enter the desired parameter name and value, then press 'Modify' to update the corresponding parameter in the list, or add a new one. To delete a parameter, press 'Delete'. **Deleting default server parameters is not recommended!**
<hr>

#### Controls Tab

The controls tab allows you to connect to a Ceruleus instance, pause and unpause the Ceruleus loop and touch off the script.

![controls.png](ceruleus_client_pics%2Fcontrols.png)

- Enter the 'Host' and 'Port' details (if required) and press 'Connect' to connect to a running Ceruleus instance. The connection light beside the status bar will change color to yellow, then green once the connection is established. The first column of the semaphore should update with non-black colors reflecting the status of the script shortly thereafter.
- Once a Ceruleus instance is connected, the left column of the Semaphore and the toggle positions will update, and it will be possible to toggle the 'Semaphore' in order to pause and unpause Ceruleus. Three semaphore checkpoints are presently implemented:
  - **webui:** Just before calling the text-generation-webui API
  - **squire:** Just before running a Squire instance
  - **pause:** Just before beginning any new subtask
- A red light (with toggle set to the right) means that the script will pause prior to the labelled subtask. A green light (with toggle set to the left) means that the script will continue there.
- When the Ceruleus loop reaches a checkpoint, a light in the right column will flash briefly. It will flash green if execution moves past the checkpoint, while it will intermittently flash yellow so long as the loop remains paused there.
- The path to squire output should be set correctly by default. If your squire instance is installed elsewhere, you must enter its path in the text box, or by finding the file with 'Browse'.
- When you first connect to a new Ceruleus instance, the pause toggle should be set to the right (red light, stop) by default. To begin execution, set this toggle to the left (green light, pass), then press 'Touch'. The 'Touch' click is ignored while a general pause is in effect.
- Press 'Disconnect' to terminate high-level communication between the connected Ceruleus instance and the GUI. This will affect 'Connection' and 'Status' tab, but not log updates.

<hr>

#### Status Tab
    
The status tab shows a record of subtask execution with respect to time and allows this data to be exported. So long as data recording is enabled, subtask data will update regardless of whether the tab is active.
![status.png](ceruleus_client_pics%2Fstatus.png)

- After connecting to a Ceruleus instance, press the green 'Record' button to begin updating the status data. This button will switch to a red 'Pause' button when recording is active.
- Press 'Pause' to pause the recording. Pressing 'Record' again will continue the recording, appending new data to the previous interval.
- Pressing 'Clear' will clear the data.
- To export subtask data for offline analysis, press 'Save Data'
- To save the graph image only, press 'Save Image'

<hr>

#### Log Tab

The log tab allows for monitoring or analysis of a Ceruleus logfile, with basic filtering if desired.

![log.png](ceruleus_client_pics%2Flog.png)

- Click 'Browse' to find the log file (usually `logfile.log` in the Ceruleus directory), then click 'Load' to load it. A green 'V' will appear once the file is loaded.
- Use the 'Log Filters' elements to filter the output for easier viewing:
  - 'Include item', if not empty, should contain one string that must be included for a line entry to be displayed
  - 'Ignore list', if not empty, should contain a comma-delimited list of strings that, if found in a line, will preclude it from being displayed.
  - Click 'Apply' to apply the current filter, and Clear to remove any applied filters.
  - Check 'Remove Filtered Text' for the string defining 'Include item' to be redacted from the included line
- Check 'Live Update' to update the displayed log every second or so.

<hr>

#### Results Tab

The results tab allows for the viewing and modification of template, result and work files.

![results.png](ceruleus_client_pics%2Fresults.png)

- The filesystem tree on the left will include all files in the 'results', 'templates' and 'work' directories:
  - Items in 'results' are cumulative lists of intermediate outputs.
  - Items in 'templates' are the templates used within Ceruleus to prepare prompts, and may be modified to change the behavior of the 'co-processing' LLM in a desired fashion.
  - Items in 'work' are intermediate results that are used within Ceruleus for prompt preparation. These are updated as the loop runs.
- To select an element of interest, click on it in the filesystem tree and press 'Open'. The text box will populate with the contents of the element.
- If you have modified an element and wish to save your changes, press 'Save'
- Elements in the 'results' and 'work' directories have default states. These can be restored using the 'Regenerate' button. This is especially useful for initializing the persistent 'results' files, as these are never cleared automatically. Press 'Save' after pressing 'Regenerate' in order to write the initialized file.

### No-GUI Instructions

- **Initializing:** Run `python main.py` from the root directory of the script.
- **Beginning execution:** 
  1. Navigate to the root directory of Ceruleus if required
  2. Type `python unpause.py`, optionally passing `--host` and `--port` if Ceruleus is running somewhere other than localhost:1230
  3. Type `touch squire_output/out.txt`. Alternatively, overwrite squire_output_out.txt with a file containing an initial answer message of your choice (e.g.: "No answers yet. Ask a question in your reply.")
- **Stopping the script:** Ceruleus runs as a typical asynchronous Python script, but has no user interface or defined stop condition. Stop Ceruleus with 'control-C' once it has generated the desirable amount of output in your chat agent's persistent log. 
- **Checking the chat log:** You can check the log by reloading the character periodically in text-generation-webui - the chat does not auto-update. 
- **Using intermediate results:** The \*.json files in the 'results' and 'work' directories can be interrogated at any time for use in downstream applications such as summarization and separate LLM-powered goal-setting.

## Afterword

I hope that this tool enhances your LLM-powered chat agents, and you find it both useful and simple to use. Please do not hesitate to contact me via this repository if you have any questions or encounter any issues with the software. ADMC Science and Consulting would be happy to further tailor Ceruleus to your needs and provide priority support. [Contact us](mailto:alexander@admedicalcorp.com) via email for details!




