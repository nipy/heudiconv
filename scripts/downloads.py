import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
sns.set_theme(style='whitegrid')

df = pd.read_csv('../data/pypi-bigquery-results.csv',
	index_col=1,
	parse_dates=True,
	)
df = df.rename(columns={'num_downloads':'Weekly Downloads'})
df['Year'] = df.index.year
df['Month'] = df.index.month

# Only whole years, hard-coding for now.
df = df[~df['Year'].isin([2017,2023])]

sns.swarmplot(data=df,
	x='Month',
	y='Weekly Downloads',
	hue='Year',
	palette='flare',
	)
plt.yscale('log')

plt.savefig('../figs/downloads.pdf')
