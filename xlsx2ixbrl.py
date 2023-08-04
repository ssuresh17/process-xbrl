from xlsx2html import xlsx2html
from bs4 import BeautifulSoup
import csv
import pprint
import html
import os
import conf
import argparse
'''''''''''''''''''''''''''''''''
    Utility functions here
'''''''''''''''''''''''''''''''''

# is the cell valid?
def is_valid_cell(s):
    return s is not None and s.string[0] in conf.valid_chars

# get new cell value from old cell value
def process_cell(td, sheet_name, name, context):
    id = td['id']
    col = id[len(sheet_name) + 1]
    # calc context
    # context = conf.ix_context[col] if col in conf.ix_context else "I20220630"
    try:
        outstring = td.string
        outstring_int = td.string
        if td.string[0] == "$":
            dollar = "$"
            outstring = td.string[1:]
            outstring_int = td.string[1:]
        else:
            dollar = ""
        if outstring[0] == "-":
            minus = "-"
            sign = ' sign="-"'
            outstring = outstring_int[1:]
        else:
            minus = ""
            sign = ""
        if td.string == "-" or td.string == "$ -":
            minus = ""
            sign = ""
            value = ''
            # value = ' value="0"'  -- Arelle throwing error when I use this
            format = 'ixt:fixed-zero'
            outstring = "-"
        else:
            format = 'ixt:num-dot-decimal'
            value = ""
        row = id[(len(sheet_name)+2):]
        
        cell_id = col + row
        id = sheet_name.replace(" ","_") + "_" + cell_id
        content = f'{dollar}{minus}<ix:nonFraction contextRef="{context}" name="{name}" unitRef="USD" id="{id}" decimals="0" format="{format}"{sign}{value}>' + \
            outstring + '</ix:nonFraction>'
        return content
    except Exception as e:
        return None


'''''''''''''''''''''''''''''''''
    Main code here
'''''''''''''''''''''''''''''''''

# Parse command line first
parser = argparse.ArgumentParser()
parser.add_argument('--i', type=str, metavar="input_file(xlsx)", required=True, help="Input xlsx file name")
parser.add_argument('--o', type=str, metavar="output_file(html)", help="Output html file name")

args = parser.parse_args()

if args.i:
    input_file = args.i
if args.o:
    output_file = args.o
else:
    output_file = input_file.split(".")[0] + ".html"

# Parse Context first
try:
    xlsx2html("contexts.xlsx", "temp")
except:
    print("No context file!")
    exit(0)
with open("temp", 'r') as f:
    html = f.read()
    # Remove header
html = html.replace(conf.original_header, '')
    # Analyze
soup = BeautifulSoup(html, 'html.parser')
context_skip_lines = 1
i = 0
context_name_map = {}
context_ref_map = {}
for tr in soup.find_all('tr'):
    # Skip some lines
    if i < context_skip_lines:
        i += 1
        continue

    tds = tr.findAll('td')
    if len(tds) == 5:
        scope = tds[0].string.strip().lower()
        statement = tds[1].string.strip().lower()
        header = tds[2].string.strip().lower()
        name = tds[3].string.strip()
        ref = pprint.pformat(tds[4].contents)
        ref_index = ref.find("<xbrli:context")
        if ref_index == -1: #critical error : invalid xbrli content
            continue
        ref = ref[ref_index:-1]
        # calculate index
        index = f"{scope}@{statement}"
        # Add to context name map
        if not index in context_name_map:
            context_name_map[index] = {}
        context_name_map[index][header] = name
        # Add to context ref map
        if not index in context_ref_map:
            context_ref_map[index] = {}
        context_ref_map[index][header] = ref

# Read Sheets
sheet_count = 0
while True:
    try:
        xlsx2html(input_file, f"temp{sheet_count}",sheet=sheet_count)
        sheet_count += 1
    except IndexError:
        break
    except:
        print("File not exists or bad format")
        exit(0)


# Process sheets
html_in = ""
ix_header_content = ""
for i in range(sheet_count):
    with open(f"temp{i}", 'r') as f:
        html = f.read()

    # Get rid of header generated by the xlsx2html library
    html_trunc = html.replace(conf.original_header, '')

    # Parse html
    soup = BeautifulSoup(html_trunc, 'html.parser')
    sheet_name = None

    name = None
    statement_scope = None
    header_row = None # row of header of the table
    header_titles = {} # dict of header titles "col" -> "title"
    for td in soup.find_all('td'):
        id = td['id']
        # Get sheet name
        if sheet_name is None:
            sheet_name = td['id'].split("!")[0]
        if "F9" in id:
            a = 6
        # Add text-align to all cells
        if is_valid_cell(td):
            td['style'] = td['style'] + ';text-align:right; font-size:12.5px'
        else:
            td['style'] = td['style'] + ';font-size:14px'
        # Calculate Column
        col = id[len(sheet_name) + 1]
        row = int(id[(len(sheet_name) + 2):])
        # Calculate Statement
        if col + str(row) == "B2":
            statement_scope = td.string.strip().lower()
        if col + str(row)  == "B3":
            statement_scope = statement_scope + "@" + td.string.strip().lower()
        # Calculate header titles
        if row == header_row:
            header_titles[col] = td.string.strip().lower()

        # Process column A
        if col == 'A':
            name = td.string.strip()
            if name == "XBRL Element":
                header_row = row
        # Process other columns
        elif col > 'B' and name and is_valid_cell(td):
            try:
                ht = header_titles[col].strip().lower()
                context_name = context_name_map[statement_scope][ht]
                #Fund balances at the bottom of the Statement of Revenues, Expenditures, and Changes in Fund Balances Need to Point to Instant Contexts Not Duration Contexts
                if name in conf.d_to_i_contexts and context_name and context_name[0] == 'D':
                    context_name = "I" + context_name[1:]
            except:
                context_name = 'I20220630'
                print(f"Invalid scope for {id}, {statement_scope}, {ht}")

            content = process_cell(td, sheet_name, name, context_name)
            if content:
                td.string = content
    
    # Remove column A
    for td in soup.find_all('td'):
        id = td['id']
        # Calculate Column
        col = id[len(sheet_name) + 1]
        if col == 'A':
            td.decompose()

    # Replace sheet name if contains space
    if " " in sheet_name:
        for td in soup.find_all('td'):
            id = td['id']
            new_id = id.replace(" ", "").replace("!", "_")
            td['id'] = new_id
    # calculate ix_header_content
    for header,ref in header_titles.items():
        if header and  ref and statement_scope:
            try:
                ix_header_content += "\n" + context_ref_map[statement_scope][ref]
            except:
                print("Invalid ix header for ", sheet_name, statement_scope, ref)

    html_in += soup.prettify("utf-8").decode("utf-8")
# Calculate ix_header
ix_header = conf.ix_header_start + ix_header_content +  conf.ix_header_end
# Replace default html header tag with the one required for Inline XBRL
html_out = conf.new_header + '\n' + ix_header.replace("$place_id$", conf.place_id) + '\n'

for line in html_in.splitlines():
    html_out = html_out + line + '\n'

# Add closing tags
html_out = html_out + '</body></html>'

# Replace escaped versions of < and > with the real versions and get rid of the string "Sheet1!" from td ids
html_out = html_out.replace("&lt;", "<")
html_out = html_out.replace("&gt;", ">")
html_out = html_out.replace(f"{sheet_name}!", f"{sheet_name}_")

#Replace some context tags to get proper cases
html_out = html_out.replace("xbrli:startdate", "xbrli:startDate")
html_out = html_out.replace("xbrli:enddate", "xbrli:endDate")

#This needs a better implementation; just using a kludge for now
#Fund balances at the bottom of the Statement of Revenues, Expenditures, and Changes in Fund Balances Need to Point to Instant Contexts Not Duration Contexts
# html_out = html_out.replace('contextRef="D20220630_GeneralFundMember" name="acfr:FundBalance"','contextRef="I20220630_GeneralFundMember" name="acfr:FundBalance"')
# html_out = html_out.replace('contextRef="D20220630_FundIdentifierDomain_Landscape" name="acfr:FundBalance"','contextRef="I20220630_FundIdentifierDomain_Landscape" name="acfr:FundBalance"')
# html_out = html_out.replace('contextRef="D20220630_FundIdentifierDomain_Housing" name="acfr:FundBalance"','contextRef="I20220630_FundIdentifierDomain_Housing" name="acfr:FundBalance"')
# html_out = html_out.replace('contextRef="D20220630_FundIdentifierDomain_ARPA" name="acfr:FundBalance"','contextRef="I20220630_FundIdentifierDomain_ARPA" name="acfr:FundBalance"')
# html_out = html_out.replace('contextRef="D20220630_FundIdentifierDomain_Capital" name="acfr:FundBalance"','contextRef="I20220630_FundIdentifierDomain_Capital" name="acfr:FundBalance"')
# html_out = html_out.replace('contextRef="D20220630_FundIdentifierDomain_Other" name="acfr:FundBalance"','contextRef="I20220630_FundIdentifierDomain_Other" name="acfr:FundBalance"')
# html_out = html_out.replace('contextRef="D20220630_GovernmentalFundsMember" name="acfr:FundBalance"','contextRef="I20220630_GovernmentalFundsMember" name="acfr:FundBalance"')



with open(output_file, 'w') as f:
    f.write(html_out)
    print(f"Successfully converted to {output_file}")
# Remove temp file
for i in range(sheet_count):
    os.remove(f"temp{i}")
os.remove("temp")
# Arelle functionality requires downloading and installing Arelle
# These commands are intended to validate and display the processed xbrl file in the Javascript viewer
# os.system('"C:\\Program Files\\Arelle\\arellecmdline" --file=D:\\xlsx2ixbrl\\ca_clayton_2022.html --plugins EdgarRenderer')

# This does not work - the idea is to start Arelle's web server and then view the file in Chrome
# os.system('"C:\\Program Files\\Arelle\\arelleCmdLine" --webserver=localhost:5to check 1053')
# os.system('Start chrome /profile-directory="Default" "http://localhost:51053/1/ix.html?doc=ca_clayton_2022.html&xbrl=true?redline=true"')
