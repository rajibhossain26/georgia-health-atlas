-- County-level CDC PLACES 2025 estimates for Georgia (age-adjusted prevalence, % of adults)
DROP TABLE IF EXISTS county;
CREATE TABLE county (
    countyfips  TEXT PRIMARY KEY,   -- 5-digit state + county FIPS
    county      TEXT NOT NULL,
    pop         INTEGER NOT NULL,   -- total population
    lon         REAL NOT NULL,      -- county centroid
    lat         REAL NOT NULL,
    diabetes    REAL,  -- diagnosed diabetes
    obesity     REAL,
    chd         REAL,  -- coronary heart disease
    stroke      REAL,
    bphigh      REAL,  -- high blood pressure
    csmoking    REAL,  -- current smoking
    lpa         REAL,  -- no leisure-time physical activity
    access2     REAL,  -- no health insurance, ages 18-64
    checkup     REAL,  -- routine checkup in past year
    depression  REAL,
    ghlth       REAL,  -- fair or poor self-rated health
    disability  REAL,  -- any disability
    foodinsecu  REAL,  -- food insecurity in past 12 months
    housinsecu  REAL,  -- housing insecurity in past 12 months
    lacktrpt    REAL,  -- lack of reliable transportation
    loneliness  REAL
);

DROP TABLE IF EXISTS county_index;
CREATE TABLE county_index (
    countyfips      TEXT PRIMARY KEY REFERENCES county(countyfips),
    chronic_burden  REAL,  -- mean z-score of diabetes, obesity, CHD, stroke, high blood pressure
    social_needs    REAL,  -- mean z-score of food/housing insecurity, lack of transport, no insurance
    lisa_quadrant   TEXT,  -- local Moran's I cluster type for chronic_burden
    lisa_p          REAL
);
