# boozook
Tools for extracting and editing Coktel Vision game resources

# Features
* Decompile game scripts partially (TOT/0OT)
* Extract and Rebuild game resources (STK)
* Image extraction partially

# Upcoming Features
* extract images with correct colors.
* decompile scripts such that all file have purpose and the output can be understood (TOT/0OT).
* recompile Game scripts.

# Suported games by boozook
* Adi 4 (DEV6)
* Adi 5 (DEV7)
* Adibou 1
* Adibou 2 (DEV6)
* Adibou 3 (DEV7)
* Adibou presente series (DEV7)
* Adiboud'chou series (DEV7)
* Geisha
* Goblins 1
* Gobliins 2
* Gobliiins 3
* Woodruff
* Croustibat
* Fascination

## Installation
[IMPORTANT] check if Python 3 is already installed on your System.
1. Install [poetry](https://python-poetry.org/)
2. Install dependencies by running poetry install
3. Activate virtual environment by running poetry shell

# Script decompiler
* To decompile TOT Scripts you have to run this command:
* python -m boozook.codex.decomp_tot path\to\game\directory *.TOT (replace there *.TOT with the name of the TOT Script including TOT extension, after that an folder called scripts gets created that stores the output from the Script.)

# Extract Game resources
* To extract the Game resources (STK) use this command:
* python -m boozook.archive -e PATH/TO/GAME/DIR

# Rebuild Game resources
To rebuild the extracted Game resources use this command:
* 

# Text extraction
* To extract Text of an Script use this comnmand:
* python -m boozook.text path/to/game/directory (after that in boozook's directory an new folder called text creates that contains 2 files, cat.tsv is for object names, and tot.tsv for the text of the dialouge)
* To recompress now the modified text back into an STK use this command.
* python -m boozook.text /path/to/game/directory -r (after that you have an folder called an texts)

# Graphics extraction
* To extract Graphics / Pictures use this command:
* python -m boozook.graphics /path/to/game
