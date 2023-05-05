import os
import pandas as pd
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.dates import YearLocator, DateFormatter
sns.set_theme(style='whitegrid')

filename = os.path.splitext(os.path.basename(__file__))[0]

# Download Data
df = pd.read_csv('../data/pypi-bigquery-results.csv',
	index_col=1,
	parse_dates=True,
	)
## Organize columns with correct types:
df['year'] = df.index.year
df['month'] = df.index.month
df['Year'] = [f"{a}-{b}" for a,b in zip(df["year"],df["month"])]
df['Year'] = pd.to_datetime(df['Year'], infer_datetime_format=True)
df = df.rename(columns={'num_downloads':'Downloads'})
df = df.drop(columns=['year', 'month'])
df.index.names = ['date']


# Etelametry Data
df_et = pd.read_csv('../data/etelemetry.csv',
	index_col=1,
	parse_dates=True,
	)
## Create value column
df_et['User Sessions'] = df_et.index
## Organize columns with correct types:
df_et['date'] = pd.to_datetime(df_et['year-week'] + "0", format="%Y-%W%w")
df_et['month'] = df_et['date'].map(lambda x: x.month)
df_et['year'] = df_et['date'].map(lambda x: x.year)
df_et['Year'] = [f"{a}-{b}" for a,b in zip(df_et["year"],df_et["month"])]
df_et['Year'] = pd.to_datetime(df_et['Year'], infer_datetime_format=True)
df_et = df_et.drop(columns=['year-week', 'year', 'month'])
df_et = df_et.set_index(['date']).sort_index()
## Filter data by date cap:
df_et = df_et.loc[:'2023-04-01']


# Merge data and reformat to long
df = pd.merge(df, df_et, on=['Year'], how='outer')
df = pd.melt(df, id_vars=['Year'], value_vars=['Downloads', 'User Sessions'])
df = df.rename(columns={'value':'Weekly Count'})
df = df.rename(columns={'variable':'Metric'})


# Plotting
ax = sns.lineplot(data=df,
	x='Year',
	y='Weekly Count',
	hue='Metric',
	markers=True, dashes=False,
	)
plt.yscale('log')
## Only keep years on xaxis (safety/redundancy, labels get duplicated if range is too small):
ax.xaxis.set_major_locator(YearLocator())
ax.xaxis.set_major_formatter(DateFormatter("%Y"))


# Save
plt.savefig(os.path.join('..','figs',f'{filename}.pdf'))
