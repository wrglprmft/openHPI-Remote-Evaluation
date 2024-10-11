# openHPI-Remote-Evaluation
A python script, that sends source files to codeocean for evaluation

I like to work on the exercises in openHPI programming courses locally in an editor/development environment. After completion, you are faced with the task of updating the files in codeocean. For this purpose, codeocean offers a ‘CodeOcean Remote Client’ in the form of three shell scripts.

There is probably no way to download the tasks automatically. Therefore, you have to start each task at least once in codeocean (via openHPI). From codeocean you can download all required files as .zip files. These should be unpacked into a separate directory, i.e. one directory per .zip task. e.g:

```
PYTHON2024_1.1_WILLKOMMEN
│ .co
│ Task.txt
│ sipl11_skript1.py
│ sipl11_skript2.py
│
└────.scripts
        macos.sh
        ubuntu.sh
        windows.ps1
```


You can then edit the Python files with your favourite tool and then upload and evaluate them with one of the shell scripts from the .scripts directory. How to call them (PowerShell does not allow the execution of scripts by default, for example) is described in the scripts themselves right at the beginning.

The scripts save the files on codeocean, start the evaluation and throw an unformatted json string at your feet as a response, which contains the result.

Technically, the scripts read the .co file, which looks something like this:

```
ABCdEfghi1j2KLMnO34pqR
https://codeocean.openhpi.de/evaluate
sipl11_skript1.py=4711
sipl11_skript2.py=0815 
```

and the Python files and generate a json:

```
{
    ‘remote_evaluation": {
        ‘validation_token": “ABCdEfghi1j2KLMnO34pqR”,
        ‘files_attributes": {
            ‘0": {
                ‘file_id": 4711,
                ‘content": ’Content of the file sipl11_skript1.py as a string’
            },
            ‘1": {
                ‘file_id": 0815,
                ‘content": ’Content of the file sipl11_skript2.py as string’
            }
        }
    }
}
```

The validation token is in the first line of the .co file.
This json is then sent UTF-8 encoded to the url from the second line of the .co file via HTTP mail. Codeocean then also responds with a json. Here is the answer for task 1.6 :

```
[
    {
        ‘file_role": “teacher_defined_test”,
        ‘waiting_for_container_time": 0.194669776,
        ‘stdout": “”,
        ‘stderr": ’test01 (sipl16_test.script1) ... ok\ntest02 (sipl16_test.script1) ... ok\ntest03 (sipl16_test.script1) ... ok\ntest04 (sipl16_test.script2) ... ok\ntest05 (sipl16_test.script2) . ... ok\ntest06 (sipl16_test.Script2) ... ok\ntest07 (sipl16_test.Script2) ... ok\n\n----------------------------------------------------------------------\nRan 7 tests in 0.003s\n\nOK\n’,
        ‘exit_code": 0,
        ‘container_execution_time": 0.460788895,
        ‘status": “ok”,
        ‘count": 7,
        ‘failed": 0,
        ‘error_messages": [],
        ‘passed": 7,
        ‘score": 1.0,
        ‘filename": “sipl16_test.py”,
        ‘message": ’Well done. All tests have been passed.’,
        ‘weight": 7.0,
        ‘hidden_feedback": false
    }, {
        ‘file_role": “teacher_defined_test”,
        ‘waiting_for_container_time": 0.194669776,
        ‘stdout": “”,
        ‘stderr": ’test08 (sipl16_testbonus.script3) ... ok\ntest09 (sipl16_testbonus.script3) ... ok\ntest10 (sipl16_testbonus.script3) . ... ok\ntest11 (sipl16_testbonus.script3) ... ok\ntest12 (sipl16_testbonus.script4) ... ok\ntest13 (sipl16_testbonus.script4) ... ok\ntest14 (sipl16_testbonus.script4) ... ok\ntest15 (sipl16_testbonus.script4) ... ok\ntest16 (sipl16_testbonus.script4) ... ok\ntest17 (sipl16_testbonus.script4) ... ok\n\n----------------------------------------------------------------------\nRan 10 tests in 0.005s\n\nOK\n’,
        ‘exit_code": 0,
        ‘container_execution_time": 0.460988714,
        ‘status": “ok”,
        ‘count": 10,
        ‘failed": 0,
        ‘error_messages": [],
        ‘passed": 10,
        ‘score": 1.0,
        ‘filename": “sipl16_testbonus.py”,
        ‘message": ’Well done. All tests have been passed.’,
        ‘weight": 0.0,
        ‘hidden_feedback": false
    }
]

```
You actually have all the information you need there.

There are many ways to use this. You can learn to quickly recognise what is going on from the json, or you can save the json to a file and then post-process this file (e.g. using a Python script) to get a more readable output. 
This is where this script comes into place, that also handles the communication. The execution of this script (evaluate_remote.py) can be set as default build task in VSCode, so that (under Windows) CTRL-SHIFT-B submits the files:

```
{
    // See https://go.microsoft.com/fwlink/?LinkId=733558
    // for the documentation about the tasks.json format
    ‘version": “2.0.0”,
    ‘tasks": [
        {
            ‘label": “submit_to_codeocean”,
            ‘type": “shell”,
            ‘command": “python ${workspaceFolder}\\evaluate_remote.py ${fileDirname}”,
            ‘problemMatcher": [],
            ‘group": {
                ‘kind": “build”,
                ‘isDefault": true
            }
        },
        {
            ‘label": “submit via Powershell Script”,
            ‘type": “shell”,
            ‘command": “powershell.exe -noprofile -executionpolicy bypass -file ${fileDirname}\\.scripts\\windows.ps1 ${fileDirname}”,
            ‘problemMatcher": [],
        }
    ]
}

```
The script comes without documentation and ‘as is’ and can in no way be considered an example of good Python programming. It also changes frequently as I can never decide if I like the current programme structure, let alone the output. It only uses standard modules, so you shouldn't have to ‘pip’. I have only tested with Python >= 3.10.
