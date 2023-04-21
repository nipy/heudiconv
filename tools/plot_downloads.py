# load data
import os
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('../pypi-bigquery-results.csv',
    index_col=1,
    parse_dates=True,
)
# df.rename(columns={"num_downloads": "downloads"})
df['rolling average'] = df.rolling(40).mean()
df.dropna(inplace=True) #removing null data
df = df.rename(columns={"num_downloads": "downloads/week"});

# plot
import matplotlib.pyplot as plt

ax = df[['downloads/week']].plot(style='.', markersize=3)
df[['rolling average']].plot(ax=ax, style='-')
plt.yscale('log')
plt.show()
