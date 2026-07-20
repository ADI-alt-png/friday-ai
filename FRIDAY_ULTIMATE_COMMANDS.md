# FRIDAY Ultimate Commands

Run old FRIDAY:

```text
start_friday.bat
```

Or in VS Code terminal:

```text
python friday.py
```

## Action-first Commands

FRIDAY now tries to do the task first. If a command is not hardcoded, it asks the API to convert your request into an action plan, then runs a local tool.

## Web / Current Info

```text
tell me todays news
latest news
news headlines
latest cricket score
weather delhi
search python projects
google ai tools
look up windows shortcuts
```

## Apps / Folders / System Locations

```text
open chrome
open vs code
open notepad
open calculator
open downloads
open documents
open desktop
open settings
open control panel
open recycle bin
open folder downloads
open file D:\path\file.txt
list folder downloads
```

## Phone Remote

```text
connect phone
phone remote
open phone control
phone link
```

When FRIDAY starts, it prints a phone link like:

```text
[PHONE REMOTE] http://YOUR-LAPTOP-IP:8765/?key=SECRET
```

Open that link in your phone browser while phone and laptop are on the same Wi-Fi.
The phone page can type commands, use the phone voice button if the browser supports it, and send those commands to the laptop FRIDAY.
The latest link is also saved here:

```text
D:\python exp\friday ai\friday_output\phone_remote_link.txt
```

## Typing / Writing

```text
write hello this is friday
type this text into the active app
type in search as iron man friday
press enter key
click submit
click on search
```

## Files

```text
create file notes with remember to study at 8 pm
append file notes with second line
make interface for daily tasks
make window for my study plan
```

Files and generated interfaces are saved in:

```text
D:\python exp\friday ai\friday_output
```

## File Index / Project Brain

```text
index folder downloads
scan folder documents
index files in D:\path\project
search files for homework
find in files api key
ask files what is this project about
ask indexed files where is the login code
question from files what should I edit
```

Notes:
- Index stores readable snippets in `friday_output\file_index.json`.
- Search results print full paths in the FRIDAY terminal.

## Tasks / Reminders

```text
remind me in 15 minutes to drink water
remind me in 2 hours to check email
remind me at 6 pm to study physics
add task complete maths homework
new task call friend
list tasks
show tasks
complete task 1
finish task 1
```

Tasks are saved in:

```text
D:\python exp\friday ai\friday_output\tasks.json
```

## Dashboard / History

```text
open dashboard
friday dashboard
open friday dashboard
show dashboard
command history
show command history
what did i say
```

Dashboard file:

```text
D:\python exp\friday ai\friday_output\friday_dashboard.html
```

## Screen

```text
see my screen
read my screen
analyze screen
summarize screen
find submit on screen
start live screen
stop live screen
```

## App / File Reader And Q&A

```text
read current app
read active app
read current window
read file explorer
read selected file
read selected text
read selection
read file D:\path\notes.txt
read folder downloads
summarize current app
summarize file D:\path\notes.txt
summarize folder downloads
ask screen what is written here
ask app what should I click next
ask context what is the deadline
ask file D:\path\notes.txt about what is the deadline
what did you read
```

Notes:
- For any app/File Explorer, FRIDAY uses screen OCR, so visible text works best.
- For files, FRIDAY can read text/code/markdown/json/csv/html/docx/xlsx and image text by OCR. PDF works if pypdf/PyPDF2 is installed.
- Last loaded content is saved in `friday_output\last_context.txt`.

## Google Learning / Research Memory

```text
learn about AI assistants
google learn about Python automation
research latest coding tools
start learning
start learning about AI assistants, Windows automation
stop learning
what have you learned
ask learned what did you learn about AI assistants
ask research what is new in coding tools
```

Notes:
- Auto learning starts with FRIDAY and runs in background.
- It uses Google News RSS in a controlled way and saves notes in `friday_output\research_memory.json`.
- It does not randomly click websites or install/change anything by itself.

## System Command Runner

```text
run command ipconfig
run command tasklist
run powershell get-process
run powershell get-date
```

Dangerous delete/format/shutdown style commands are blocked.

## Email / Gmail

```text
open email
open gmail
gmail kholo
add email contact rahul as rahul@example.com
write email to rahul subject homework body I completed the work
compose email to rahul saying I will call you later
send email
confirm send email
```

Notes:
- `send email` only asks confirmation.
- `confirm send email` presses Gmail send shortcut in the active Gmail compose window.

## Coding

```text
open python compiler
python compiler kholo
open online compiler python
write python code for calculator
code likh python factorial ke liye
create python file for snake game
open compiler and code python hello world
```

Notes:
- `write code...` pastes generated code into the active editor/compiler.
- `create python file...` saves generated code in `friday_output`.
- For best results, open/click the online compiler editor first, then say the code command.

## Safe Power Controls

```text
shutdown
confirm shutdown
restart
confirm restart
```

## Notes

- FRIDAY is more action-first now, but no assistant can literally do every possible task perfectly.
- If a task needs a new window/interface, say `make interface for ...`.
- If it needs to type somewhere, open/click the target field first, then say `write ...`.
