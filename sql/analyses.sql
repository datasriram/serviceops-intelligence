-- name: daily_volume
-- How many requests arrive each day?
SELECT date(created_at) AS day,
    COUNT(*) AS requested
FROM bookings
GROUP BY 1;
-- name: monthly_kpis
-- How does monthly fulfillment change?
SELECT substr(created_at,1,7) AS month,
    COUNT(*) AS requested,
    COUNT(assigned_at) AS accepted,
    SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
    AVG(CASE WHEN status='completed' THEN 1.0 ELSE 0 END) AS fulfillment
FROM bookings
GROUP BY 1;
-- name: cancellations
-- Where are cancellations concentrated?
SELECT location,service,
    COUNT(*) AS requested,
    AVG(CASE WHEN status='cancelled' THEN 1.0 ELSE 0 END) AS cancellation_rate
FROM booking_fact
GROUP BY 1, 2;
-- name: hourly_weekly_demand
-- When does demand arrive?
-- Consistent with pandas/Excel: 0=Monday through 6=Sunday.
SELECT (CAST(strftime('%w',created_at) AS INTEGER)+6)%7 AS weekday,
    CAST(strftime('%H',created_at) AS INTEGER) AS hour,
    COUNT(*) AS requested
FROM bookings
GROUP BY 1, 2;
-- name: assignment_delays
-- How long do accepted requests wait?
SELECT location,
    COUNT(assigned_at) AS accepted,
    AVG((julianday(assigned_at)-julianday(created_at))*1440) AS assignment_minutes
FROM booking_fact
GROUP BY 1;
-- name: utilization
-- What share of shift time is spent on service?
WITH busy AS (SELECT shift_id,
    SUM((julianday(completed_at)-julianday(start_at))*1440) AS busy_minutes
FROM bookings
WHERE status='completed'
GROUP BY shift_id)
SELECT s.location_id,substr(s.start_at,1,7) AS month,
    SUM(COALESCE(b.busy_minutes,0)) AS busy_minutes,
    SUM((julianday(s.end_at)-julianday(s.start_at))*1440) AS available_minutes,
    SUM(COALESCE(b.busy_minutes,0))/SUM((julianday(s.end_at)-julianday(s.start_at))*1440) AS utilization
FROM shifts s
LEFT JOIN busy b USING(shift_id)
GROUP BY 1, 2;
-- name: repeat_customers
-- How often do customers request again?
WITH history AS (SELECT customer_id,created_at,
    LAG(created_at) OVER(PARTITION BY customer_id ORDER BY created_at,booking_id) AS prior_booking
FROM bookings)
SELECT customer_id,
    COUNT(*) AS bookings,
    AVG(julianday(created_at)-julianday(prior_booking)) AS mean_days_between
FROM history
GROUP BY 1
HAVING COUNT(*)>1;
-- name: average_booking_value
-- What is the average completed booking worth?
SELECT SUM(revenue)/NULLIF(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END),0) AS average_booking_value
FROM booking_fact;
-- name: revenue_by_service
-- Which services generate revenue?
SELECT service,
    SUM(revenue) AS revenue
FROM booking_fact
WHERE status='completed'
GROUP BY 1;
-- name: margin_by_location
-- How much does each zone contribute?
SELECT location,
    SUM(revenue) AS revenue,
    SUM(worker_payout+materials+processing) AS attributable_cost,
    SUM(contribution_margin) AS contribution_margin
FROM booking_fact
GROUP BY 1;
-- name: underperforming_zones
-- Which zones fall below overall fulfillment?
WITH zones AS (SELECT location,
    COUNT(*) AS requested,
    AVG(CASE WHEN status='completed' THEN 1.0 ELSE 0 END) AS fulfillment
FROM booking_fact
GROUP BY 1)
SELECT *,
    DENSE_RANK() OVER(ORDER BY fulfillment) AS priority_rank
FROM zones
WHERE fulfillment<(SELECT AVG(CASE WHEN status='completed' THEN 1.0 ELSE 0 END)
FROM bookings);
-- name: demand_capacity_gaps
-- Where does daily request workload exceed shift time?
-- Aggregate workload proxy: not a scheduling feasibility estimate. Expected duration excludes travel.
WITH demand AS (SELECT location_id,date(created_at) AS day,
    SUM(expected_minutes) AS requested_minutes
FROM bookings
GROUP BY 1, 2), supply AS (SELECT location_id,date(start_at) AS day,
    SUM((julianday(end_at)-julianday(start_at))*1440) AS available_minutes
FROM shifts
GROUP BY 1, 2)
SELECT d.*,
    COALESCE(s.available_minutes,0) AS available_minutes,
    MAX(d.requested_minutes-COALESCE(s.available_minutes,0),0) AS gap_minutes
FROM demand d
LEFT JOIN supply s USING(location_id,day);
