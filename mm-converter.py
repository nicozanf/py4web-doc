#!/usr/bin/env python3

# mm-converter
# 
# # MarkMin Converter
#
# Usage: run it in a working folder and it will convert all the contained *.mm files to standard .md (MarkDown) files. 
#           Then it uses Pandoc on the md files in order to obtain .rst (reStructuredText) + html files
#
# note that :cite, :inxx and internal anchors are simply deleted
# 
# nicozanf@gmail.com 2020.10.18

import os
import re
import subprocess

regex_links_to_index = re.compile(r'''
                            ``            # exactly two backticks
                            [^`]*?        # any string / lines including newlines, up to the next backtick (non-greedy)
                            ``:index      # exactly two backticks + colon + index
                            ''', re.M|re.X) # Multiline and Verbose

regex_links_to_inxx = re.compile(r'''
                            ``            # exactly two backticks
                            [^`]*?        # any string / lines including newlines, up to the next backtick (non-greedy)
                            ``:inxx       # exactly two backticks + colon + inxx
                            ''', re.M|re.X) # Multiline and Verbose

regex_links_to_cite = re.compile(r'''
                            (``)            # exactly two backticks
                            ([^`]*?)        # any string / lines including newlines, up to the next backtick (non-greedy)
                            (``:cite)       # exactly two backticks + colon + cite
                            ([ ]+)?         # optional one or more spaces
                            ''', re.M|re.X) # Multiline and Verbose

regex_verbatim = re.compile(r'''
                            (?P<verbatim_start>``)          # exactly two backticks
                            (?P<verbatim_text>[^`:][^`]*?)  # not a backtick and not a colon + any strings up to the next backtick (non-greedy)
                            (?P<verbatim_stop>``)           # exactly two backticks
                            (?P<verbatim_end>[^:])          # and not a colon
                            ''', re.M|re.X)                 # Multiline and Verbose

regex_internal_links= re.compile(r'''
                            (```[^`]+```) |     # except inside a code block
                            [^`]\[\[            # not a backtick and two open square brackets
                            [^#\n]*?            # everything except a dash or newline 
                            \]\]                # two closed brackets
                            ''', re.M|re.X)     # Multiline and Verbose

regex_internal_titled_links= re.compile(r'''
                            [^`]\[\[                # not a backtick and two open square brackets
                            (?P<link_title>[^\#\n]*?) # everything except hashes and new lines
                            \#                      # a hash
                            [^\]]+?                 # any string / lines including newlines, up to the next closed brackets (non-greedy) 
                            ]]                      # two closed brackets
                            ''', re.M|re.X)         # Multiline and Verbose

regex_images= re.compile(r'''
                            <img[\s]+src=["']          #  <img src=" or '
                            (?P<image_link>.*?)          # image path and name
                            ["'][\s]+?                 # " or ' and spaces
                            (?P<image_size>.*?)?          # optional size specifications
                            [\s]*\/>                # spaces and />
                            ''', re.M|re.X)         # Multiline and Verbose

regex_block_quote = re.compile(r'''
                            \n-{4,10}\n                 # four to 10 dashes on a single line
                            (?P<block_quote>[\s\S]+?)   # next strings / lines including newlines (non-greedy)
                            \n-{4,10}\n                 # four to 10 dashes on a single line
                            ''', re.M|re.X)             # Multiline and Verbose

regex_italics = re.compile(r''' '{2}                    # exactly 2 single quote
                            (?P<italics_text>.*?)       # anything excluding newlines up to the next single quote (non-greedy)
                            '{2}                        # exactly 2 single quote
                            ''', re.X)                  # Verbose                                 

regex_inline_program_block = re.compile(r'''
                                    `{2}                         # two backticks
                                    (?P<prg_listing>[^`]+?)     # any string / lines including newlines, up to the next backtick excluded (non-greedy)
                                    `{2}:                         # and two other backticks plus colon
                                    (?P<prg_label>\w+?)         # and program language name (non-greedy)
                                    (?P<prg_end>[ .,:;])     # one space or comma or full stop or colon or semicolon
                                ''', re.M|re.X)                 # Multiline and Verbose


regex_full_program_block = re.compile(r'''
                                    ``\n                        # two backticks + Return
                                    (?P<prg_listing>[^`]*?)     # any string / lines including newlines, up to the next backtick excluded (non-greedy)
                                    ``:                         # and two other backticks plus colon
                                    (?P<prg_label>\w+?)         # and program language name (non-greedy)
                                    (?P<prg_end>\n)             # Return 
                                ''', re.M|re.X)                 # Multiline and Verbose

regex_python_no_lexer = re.compile(r'''
                                    ``\n                        # two backticks + Return
                                    (?P<prg_listing>[^`]*?)     # any string / lines including newlines, up to the next backtick excluded (non-greedy)
                                    ``:python\[lexer=          # and two other backticks plus colon and python[=lexer
                                    None                        # and lexer language name (non-greedy)
                                    \]\n                       # plus ] and Return 
                                ''', re.M|re.X)                 # Multiline and Verbose

regex_python_lexer = re.compile(r'''
                                    ``\n                        # two backticks + Return
                                    (?P<prg_listing>[^`]*?)     # any string / lines including newlines, up to the next backtick excluded (non-greedy)
                                    ``:python\[lexer='          # and two other backticks plus colon and python[=lexer'
                                    (?P<lexer_label>\w+?)       # and lexer language name (non-greedy)
                                    '\]\n                       # plus '] and Return 
                                ''', re.M|re.X)                 # Multiline and Verbose

regex_table_4col = re.compile(r'''
                                    \n={5,25}\n                         # a line with only 5 to 25 '='
                                    (?P<table_header1>[^\|\n]*)         # first line (header) - column 1
                                    \|                                  # one pipe
                                    (?P<table_header2>[^\|\n]*)         # first line (header) - column 2
                                    \|                                  # one pipe
                                    (?P<table_header3>[^\|\n]*)         # first line (header) - column 3
                                    \|                                  # one pipe                                   
                                    (?P<table_header4>[^\|\n]*)         # first line (header) - column 4
                                    \n(?P<table_content>[\s\S]+?)       # next strings / lines including newlines (non-greedy)
                                    \n={5,25}\n                         # another line with only 5 to 25 '='
                                ''', re.M|re.X)                         # Multiline and Verbose


regex_table_3col = re.compile(r'''
                                    \n={5,25}\n                         # a line with only 5 to 25 '='
                                    (?P<table_header1>[^\|\n]*)         # first line (header) - column 1
                                    \|                                  # one pipe
                                    (?P<table_header2>[^\|\n]*)         # first line (header) - column 2
                                    \|                                  # one pipe
                                    (?P<table_header3>[^\|\n]*)         # first line (header) - column 3
                                    \n(?P<table_content>[\s\S]+?)       # next strings / lines including newlines, up to the next '=' excluded (non-greedy)
                                    \n={5,25}\n                         # another line with only 5 to 25 '='
                                ''', re.M|re.X)                         # Multiline and Verbose


regex_table_2col = re.compile(r'''
                                    \n={5,25}\n                         # a line with only 5 to 25 '='
                                    (?P<table_header1>[^\|\n]*)         # first line (header) - column 1
                                    \|                                  # one pipe
                                    (?P<table_header2>[^\|\n]*)         # first line (header) - column 2
                                    \n(?P<table_content>[\s\S]+?)       # next strings / lines including newlines, up to the next '=' excluded (non-greedy)
                                    \n={5,25}\n                         # another line with only 5 to 25 '='
                                ''', re.M|re.X)                         # Multiline and Verbose


def change_verbatim(data):
    # changes verbatim to exactly three backticks
    data = data
    return re.sub(regex_verbatim, r'```\g<verbatim_text>```\g<verbatim_end>', data)

def change_block_quote(data):
    # changes quotation blocks
    data = data
    return re.sub(regex_block_quote, r'\n\n>\g<block_quote>\n\n', data)

def change_italics(data):
    # changes italics from ''whatever it is'' to _whatever it is_
    data = data
    return re.sub(regex_italics, r'_\g<italics_text>_', data)

def change_images(data):
    # changes images from html-like to markdown
    data = data
    return re.sub(regex_images, r' ![](\g<image_link>){ \g<image_size> }', data)

def remove_links_to_index(data):
    # remove liks to the index, they are useless in py4web docs
    data = data
    return re.sub(regex_links_to_index, r'', data)

def remove_links_to_inxx(data):
    # remove liks to the index, they are useless in py4web docs
    data = data
    return re.sub(regex_links_to_inxx, r'', data)

def remove_links_to_cite(data):
    # remove liks to the index, they are useless in py4web docs
    data = data
    return re.sub(regex_links_to_cite, r'', data)

def remove_internal_links(data):
    # remove internal liks if they are without title
    data = data
    return re.sub(regex_internal_links, r'\1', data)

def remove_internal_titled_links(data):
    # remove internal liks but keep the title if present
    data = data
    return re.sub(regex_internal_titled_links, r' *\g<link_title>* ', data)

def change_full_program_block(data):
    # changes a program block by moving the program language after the initial backticks
    data = data
    return re.sub(regex_full_program_block, r'```\g<prg_label>\n\g<prg_listing>```\g<prg_end>', data)

def change_python_lexer(data):
    # changes a program block by moving the program language after the initial backticks
    data = data
    return re.sub(regex_python_lexer, r'```\g<lexer_label>\n\g<prg_listing>```\n\n', data)

def change_python_no_lexer(data):
    # changes a none program block to verbatim data
    data = data
    return re.sub(regex_python_no_lexer, r'```\n\g<prg_listing>```\n\n', data)

def change_inline_program_block(data):
    # changes an inline program block by remmoving the program language and setting  three backticks
    data = data
    return re.sub(regex_inline_program_block, r'```\g<prg_listing>```\g<prg_end>', data)

def change_table_4col(data):
    # properly format tables with 4 columns
    data = data
    return re.sub(regex_table_4col, r'\n\g<table_header1>|\g<table_header2>|\g<table_header3>|\g<table_header4>\n----------|----------|----------|----------\n\g<table_content>\n\n', data)

def change_table_3col(data):
    # properly format tables  with 3 columns
    data = data
    return re.sub(regex_table_3col, r'\n\g<table_header1>|\g<table_header2>|\g<table_header3>\n---------------|----------------|----------\n\g<table_content>\n\n', data)

def change_table_2col(data):
    # properly format tables  with 2 columns
    data = data
    return re.sub(regex_table_2col, r'\n\g<table_header1>|\g<table_header2>\n---------------------|---------------------\n\g<table_content>\n\n', data)


def checkfiles():
    print('**************************************')
    print("MarkMin converter")
    print('**************************************')

    print(f"Working on folder {os.getcwd()}")
    for subdir, dirs, files in os.walk(os.getcwd()):
        for file in files:
            ext = os.path.splitext(file)[-1].lower()
            if ext == '.mm':
                convert2md(os.path.join(subdir, file))


def convert2md(file):
    print(f"    Working on file {file}")
    data = open(file, 'r').read()

    data = remove_links_to_index(data)
    data = remove_links_to_inxx(data)
    data = remove_links_to_cite(data)
    data = change_verbatim(data)
    data = change_python_no_lexer(data)
    data = change_python_lexer(data) 
    data = change_block_quote(data)
    data = change_italics(data)
    data = change_inline_program_block(data)
    data = change_full_program_block(data)
    data = remove_internal_links(data)
    data = remove_internal_titled_links(data)
    data = change_images(data)
    data = change_table_4col(data)
    data = change_table_3col(data)
    data = change_table_2col(data)


    write_files(file, data)
    
def write_files(file, data):
    for extension in ['md', 'rst', 'html']:
        ext_dir = os.path.join(os.getcwd() , extension)
        md_dir = os.path.join(os.getcwd() , 'md')
        if not os.path.isdir(ext_dir):
            os.mkdir(ext_dir)
        ext_file = os.path.join(ext_dir , os.path.splitext(os.path.basename(file))[0] + "." + extension)
        md_file = os.path.join(md_dir , os.path.splitext(os.path.basename(file))[0] + ".md")
        print(f'writing {ext_file}')
        if os.path.exists(ext_file):
            os.unlink(ext_file)
        with open(ext_file, 'w') as handler:
            write_format(extension, ext_file, handler, md_file, data)


def write_format(extension, ext_file, handler, md_file, data):
    if extension =='md':
            handler.write(data)
    elif extension =='rst':
        try:
            subprocess.call(['pandoc', '-s', md_file, '-f', 'markdown', '-t', 'rst', '-o', ext_file])
        except FileNotFoundError:
            print("\n **** ERROR ****: you need the Pandoc module installed!")
            exit(0)
    elif extension =='html':
        try:
            subprocess.call(['pandoc', '-s', md_file, '-f', 'markdown', '-t', 'html', '-o', ext_file,  '--highlight-style=kate'])
        except FileNotFoundError:
            print("\n **** ERROR ****: you need the Pandoc module installed!")
            exit(0)


if __name__ == "__main__":
    checkfiles()
