-- name: statewide_weighted
-- Population-weighted statewide prevalence (each county's adults count in proportion to its size)
SELECT
    ROUND(SUM(diabetes   * pop) / SUM(pop), 1) AS diabetes,
    ROUND(SUM(obesity    * pop) / SUM(pop), 1) AS obesity,
    ROUND(SUM(bphigh     * pop) / SUM(pop), 1) AS high_blood_pressure,
    ROUND(SUM(access2    * pop) / SUM(pop), 1) AS uninsured_18_64,
    ROUND(SUM(foodinsecu * pop) / SUM(pop), 1) AS food_insecurity,
    ROUND(SUM(lacktrpt   * pop) / SUM(pop), 1) AS lack_transport
FROM county;

-- name: top10_diabetes
-- Counties with the highest age-adjusted diabetes prevalence
SELECT county, pop, diabetes, obesity, foodinsecu AS food_insecurity, access2 AS uninsured
FROM county
ORDER BY diabetes DESC, county
LIMIT 10;

-- name: size_groups
-- Small counties (< 50,000 residents) vs larger counties, population-weighted
SELECT
    CASE WHEN pop < 50000 THEN 'Under 50,000 residents' ELSE '50,000+ residents' END AS county_size,
    COUNT(*)                                   AS counties,
    SUM(pop)                                   AS population,
    ROUND(SUM(diabetes   * pop) / SUM(pop), 1) AS diabetes,
    ROUND(SUM(chd        * pop) / SUM(pop), 1) AS heart_disease,
    ROUND(SUM(access2    * pop) / SUM(pop), 1) AS uninsured,
    ROUND(SUM(lacktrpt   * pop) / SUM(pop), 1) AS lack_transport
FROM county
GROUP BY county_size
ORDER BY county_size DESC;

-- name: double_burden
-- Counties in the top fifth for BOTH diabetes and food insecurity (window functions)
WITH ranked AS (
    SELECT county, pop, diabetes, foodinsecu,
           NTILE(5) OVER (ORDER BY diabetes)   AS diabetes_quintile,
           NTILE(5) OVER (ORDER BY foodinsecu) AS food_quintile
    FROM county
)
SELECT county, pop, diabetes, foodinsecu AS food_insecurity
FROM ranked
WHERE diabetes_quintile = 5 AND food_quintile = 5
ORDER BY diabetes DESC, county;

-- name: hot_spots
-- Counties in statistically significant chronic-disease hot spots (local Moran's I, p < 0.05)
SELECT c.county, c.pop, c.diabetes, c.obesity, c.chd,
       ROUND(i.chronic_burden, 2) AS burden_index, ROUND(i.lisa_p, 3) AS p
FROM county c JOIN county_index i USING (countyfips)
WHERE i.lisa_quadrant = 'High-High (hot spot)' AND i.lisa_p < 0.05
ORDER BY i.chronic_burden DESC;

-- name: cluster_summary
-- Population and average outcomes in each type of local cluster
SELECT CASE WHEN i.lisa_p < 0.05 THEN i.lisa_quadrant ELSE 'Not significant' END AS cluster,
       COUNT(*) AS counties,
       SUM(c.pop) AS population,
       ROUND(SUM(c.diabetes * c.pop) / SUM(c.pop), 1) AS diabetes,
       ROUND(SUM(c.foodinsecu * c.pop) / SUM(c.pop), 1) AS food_insecurity,
       ROUND(SUM(c.access2 * c.pop) / SUM(c.pop), 1) AS uninsured
FROM county c JOIN county_index i USING (countyfips)
GROUP BY cluster
ORDER BY diabetes DESC;
