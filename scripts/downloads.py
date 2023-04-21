import os
import pandas as pd
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt
sns.set_theme(style='whitegrid')

filename = os.path.splitext(os.path.basename(__file__))[0]

df = pd.read_csv('../data/pypi-bigquery-results.csv',
	index_col=1,
	parse_dates=True,
	)
df['year'] = df.index.year
df['month'] = df.index.month
df['week'] = df.index
df['Year'] = [f"{a}-{b}" for a,b in zip(df["year"],df["month"])]
df['Year'] = pd.to_datetime(df['Year'], infer_datetime_format=True)
df['week'] = pd.to_datetime(df['week'], infer_datetime_format=True)
df = df.rename(columns={'num_downloads':'Weekly Downloads'})
ax = sns.lineplot(data=df,
	x="Year",
	y="Weekly Downloads",
	markers=True, dashes=False,
	)
plt.yscale('log')

plt.savefig(os.path.join('..','figs',f'{filename}.pdf'))
