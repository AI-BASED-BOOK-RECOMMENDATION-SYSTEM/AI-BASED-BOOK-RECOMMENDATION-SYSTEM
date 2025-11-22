import pandas as pd
import os
import glob

filepath=os.getcwd()
allfiles=glob.glob(os.path.join(filepath,"*.csv"))

dflist=[]
for file in allfiles:
    df=pd.read_csv(file,header=0,index_col=None)
    dflist.append(df)

merged=pd.concat(dflist,ignore_index=True)
merged.to_csv("mergeddata.csv",index=False)

