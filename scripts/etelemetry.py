import os
import pandas as pd
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.dates import YearLocator, DateFormatter
sns.set_theme(style='whitegrid')

filename = os.path.splitext(os.path.basename(__file__))[0]

df = pd.read_csv('../data/etelemetry.csv',
	index_col=1,
	parse_dates=True,
	)
# Create value column
df['Confirmed User Sessions'] = df.index

# Organize columns with correct types:
df['date'] = pd.to_datetime(df['year-week'] + "0", format="%Y-%W%w")
df['month'] = df['date'].map(lambda x: x.month)
df['year'] = df['date'].map(lambda x: x.year)
df['Year'] = [f"{a}-{b}" for a,b in zip(df["year"],df["month"])]
df['Year'] = pd.to_datetime(df['Year'], infer_datetime_format=True)
df = df.drop(columns=['year-week','year', 'month'])
df = df.set_index(['date']).sort_index()

# Filter data by date cap:
df = df.loc[:'2023-04-01']

#Plot:
ax = sns.lineplot(data=df,
	x="Year",
	y="Confirmed User Sessions",
	markers=True, dashes=False,
	)
plt.yscale('log')

# Only keep years on xaxis:
ax.xaxis.set_major_locator(YearLocator())
ax.xaxis.set_major_formatter(DateFormatter("%Y"))

plt.savefig(os.path.join('..','figs',f'{filename}.pdf'))
