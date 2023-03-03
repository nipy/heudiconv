#standardSQL
SELECT
  COUNT(*) AS num_downloads,
  DATE_TRUNC(DATE(timestamp), WEEK) AS `week`
FROM `bigquery-public-data.pypi.file_downloads`
WHERE
  file.project = 'heudiconv'
  -- Only query the last 108 (9 years) months of history
  AND DATE(timestamp)
    BETWEEN DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 108 MONTH), MONTH)
    AND CURRENT_DATE()
GROUP BY `week`
ORDER BY `week` DESC