from utils.Context import Context
from utils.IX import IX
from utils.helper_functions import *
import pandas as pd
from utils.constants import *
from typing import * # to specify funtion inputs and outputs


class Sheet:
    """ Object to represent an Excel sheet tab (one table) """

    def __init__(self, excel_file : str, sheet_name: str, context_name_map : Dict[str, Dict[str, str]]):
        """
        Initializing a "sheet" object, which contains all information
        from the original Excel table and converts it to relevant 
        inline XBRL content
        """
        # read in sheet
        self.df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
        
        #### HARDCODING columns here ####
        self.extra_left_cols = 2
        self.city = clean(self.df.iloc[0,1])
        self.scope = clean(self.df.iloc[1,1])
        self.statement = clean(self.df.iloc[2,1])
        self.date = clean(self.df.iloc[3,1])

        # num. of lines to trim from header
        self.n_header_lines = self.df[self.df.columns[-1]].first_valid_index()

        # clean data in spreadsheet
        self.reshape_data(sheet_name)

        # Process all the cells w/ data; stored as a list of IX objects
        context_map = context_name_map[self.get_index()]
        self.data = [IX(row, context_map) for _, row in self.df.iterrows()]

        # Process the associated contexts
        context_names = set(ix.col_name for ix in self.data)
        self.contexts = {Context(context_map, self.date, col) for col in context_names}
    
    def reshape_data(self, sheet_name : str) -> None:
        """
        TODO
        """   
        # clean column names
        self.df.columns = self.df.iloc[self.n_header_lines].apply(clean)
        self.df = self.df.drop(list(range(self.n_header_lines + 1)))
        
        # Record original row number (from Excel sheet)
        self.df["row"] = self.n_header_lines + self.df.index - 3
        n_rows_orig = len(self.df) # num of rows before reshaping

        # Reshape the DataFrame        
        id_cols = self.df.columns[:self.extra_left_cols].tolist() + ["row"]
        val_cols = self.df.columns[self.extra_left_cols:].tolist()
        self.df = pd.melt(self.df, id_vars=id_cols, value_vars=val_cols, var_name="header")

        # Calculate original sheet column and cell in Excel document
        self.df['col'] = [ALPHABET[i] for i in (self.extra_left_cols + (self.df.index // n_rows_orig))]
        cells = [f'{c}{r}' for c, r in zip(self.df['col'], self.df["row"])]
        self.df["id"] = [f'{sheet_name.replace(" ", "")}_{cell}' for cell in cells]
        self.df = self.df.sort_values(by=['row', 'col'])

        print(self.df)

    def get_index(self) -> str:
        """ generate the index used for the contexts map dictionary """
        return f"{self.scope}@{self.statement}"

    def header(self) -> str:
        """Generate header text for the HTML rendering"""
        ret = ""
        for slot in ["city", "scope", "statement", "date"]:
            ret = ret + "<br>" + print_nicely(getattr(self, slot))
        return ret