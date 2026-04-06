import sys

import pandas as pd

print('args:', sys.argv)

month = int(sys.argv[1])

df = pd.DataFrame({'day': [1, 2, 3], 'num_rides': [4, 5, 6]})

df['month'] = month

df.to_parquet('output.parquet', index=False)

print(df.head())

print("Hello from the pipeline!, month:", month)