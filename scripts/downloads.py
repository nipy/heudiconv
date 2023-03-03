import pandas as pd
import seaborn as sns
from matplotlib import pyplot
sns.set_theme(style="ticks", palette="pastel")

df = pd.read_csv("../data/pypi-bigquery-results.csv",
	index_col=1,
	parse_dates=True,
	)
df = df.rename(columns={"num_downloads":"downloads"})
df['year'] = df.index.year
df['month'] = df.index.month

# Only whole years, hard-coding for now.
df = df[~df['year'].isin([2017,2023])]

print(df.columns)
print(df)


sns.boxplot(data=df,
	x="month",
	y="downloads",
	hue="year",
	)
#sns.despine(offset=10, trim=True)

pyplot.savefig("../figs/downloads.pdf")
