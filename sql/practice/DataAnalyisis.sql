1. Top 10 grounds by number of matches

Query

SELECT 
    venue,
    COUNT(DISTINCT match_id) AS matches
FROM matches
GROUP BY venue
ORDER BY matches DESC
LIMIT 10;
Answer
Rank	Ground	Matches
1	Eden Gardens	77
2	Wankhede Stadium	73
3	M Chinnaswamy Stadium	65
4	Feroz Shah Kotla	60
5	Wankhede Stadium, Mumbai	57
6	Rajiv Gandhi International Stadium, Uppal	49
7	MA Chidambaram Stadium, Chepauk	48
8	Sawai Mansingh Stadium	47
9	Dubai International Cricket Stadium	46
10	MA Chidambaram Stadium, Chepauk, Chennai	38

This query counts how many different matches were played at each ground. Then it sorts the grounds from highest to lowest and shows the top 10.


2. Grounds with average innings score above 165, minimum 25 matches

Query

WITH innings_scores AS (
    SELECT 
        m.venue,
        d.match_id,
        d.innings,
        SUM(d.total_runs) AS innings_score
    FROM deliveries d
    JOIN matches m 
        ON m.match_id = d.match_id
    WHERE d.is_super_over = 0
    GROUP BY m.venue, d.match_id, d.innings
),
venue_stats AS (
    SELECT
        venue,
        COUNT(DISTINCT match_id) AS matches,
        AVG(innings_score) AS avg_score
    FROM innings_scores
    GROUP BY venue
)
SELECT
    venue,
    matches,
    ROUND(avg_score, 2) AS avg_score
FROM venue_stats
WHERE matches >= 25
  AND avg_score > 165
ORDER BY avg_score DESC;
Answer
Ground	Matches	Average Innings Score
Arun Jaitley Stadium, Delhi	27	189.57
Eden Gardens, Kolkata	27	182.21
Narendra Modi Stadium, Ahmedabad	37	177.82
Wankhede Stadium, Mumbai	57	175.58
Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow	26	167.59


First, we calculate the score of each innings. Then we find the average score for each ground. Only grounds with at least 25 matches and an average score above 165 are included.


3. Chase win percentage for grounds with at least 50 matches

Query

SELECT
    venue,
    COUNT(DISTINCT match_id) AS matches,
    ROUND(
        100.0 * SUM(
            CASE WHEN win_by_wickets > 0 THEN 1 ELSE 0 END
        ) / COUNT(DISTINCT match_id), 2
    ) AS chase_win_percentage
FROM matches
GROUP BY venue
HAVING matches >= 50
ORDER BY chase_win_percentage DESC;
Answer
Ground	Matches	Chase Win %
Wankhede Stadium, Mumbai	57	59.65%
Eden Gardens	77	58.44%
M Chinnaswamy Stadium	65	55.38%
Feroz Shah Kotla	60	51.67%
Wankhede Stadium	73	50.68%


A chase win means the team batting second won by wickets. We calculate how many such wins happened and convert that number into a percentage. Only grounds with 50 or more matches are considered.



4. Number of unique cleaned venues

Query

SELECT COUNT(DISTINCT TRIM(venue)) AS unique_venues
FROM matches;
Answer

59 unique cleaned venues

Simple explanation:
TRIM() removes extra spaces from venue names. DISTINCT removes duplicate names. Finally, COUNT() tells us how many unique venue names remain.

Note: This is basic cleaning only. Names such as "Wankhede Stadium" and "Wankhede Stadium, Mumbai" are still treated as different names.


5. Five grounds with the lowest powerplay run rate

Query

WITH powerplay AS (
    SELECT
        m.venue,
        d.match_id,
        SUM(d.total_runs) AS runs,
        SUM(
            CASE 
                WHEN d.is_wide_ball = 0 
                 AND d.is_no_ball = 0 
                THEN 1 
                ELSE 0 
            END
        ) AS legal_balls
    FROM deliveries d
    JOIN matches m 
        ON m.match_id = d.match_id
    WHERE d.over_number BETWEEN 0 AND 5
      AND d.is_super_over = 0
    GROUP BY m.venue, d.match_id, d.innings
),
venue_stats AS (
    SELECT
        venue,
        COUNT(DISTINCT match_id) AS matches,
        1.0 * SUM(runs) / SUM(legal_balls) * 6 AS powerplay_rr
    FROM powerplay
    GROUP BY venue
)
SELECT
    venue,
    matches,
    ROUND(powerplay_rr, 2) AS powerplay_rr
FROM venue_stats
WHERE matches >= 25
ORDER BY powerplay_rr
LIMIT 5;
Answer
Rank	Ground	Matches	Powerplay Run Rate
1	Sheikh Zayed Stadium	29	7.28
2	Rajiv Gandhi International Stadium, Uppal	49	7.35
3	Sawai Mansingh Stadium	47	7.51
4	Dubai International Cricket Stadium	46	7.54
5	M Chinnaswamy Stadium	65	7.55


The powerplay is the first 6 overs. We calculate runs scored during the powerplay and convert them into runs per over. Then we select grounds with at least 25 matches and find the five lowest run rates.



6. Why is COUNT(DISTINCT match_id) safer than COUNT(*) after a JOIN?

Answer

When we join matches with deliveries, one match appears in many rows because every ball is stored separately.

For example:

1 match → 120+ delivery rows

So:

COUNT(*)

would count the delivery rows, not the number of matches.

But:

COUNT(DISTINCT match_id)

counts each match only once.

In simple words:
COUNT(*) = counts rows after the JOIN.
COUNT(DISTINCT match_id) = counts actual unique matches.



7. Why can't we answer the day/night question using match_date alone?
Answer

match_date only tells us the date when the match happened.

For example:

2025-04-15

It doesn't tell us whether the match was played:

during the day ☀️
at night 🌙
partly during day and night

To identify day/night matches, we would need match start time, match timing, or another field indicating day/night.

Simple explanation:
A date tells us "which day?", but not "what time of day?".