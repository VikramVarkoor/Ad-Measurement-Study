"""The SQL layers tested on tiny synthetic tables with hand-computed answers."""
import duckdb
import pytest

from src import paths


@pytest.fixture()
def con():
    c = duckdb.connect()
    yield c
    c.close()


class TestKpiSql:
    @pytest.fixture(autouse=True)
    def setup(self, con):
        con.execute("""
            CREATE TABLE facebook_ads AS SELECT * FROM (VALUES
                -- ad, campaign, fb, age, gender, interest, impr, clicks, spend, total, approved
                (1, 100, 1, '30-34', 'M', 1, 1000, 10, 5.0, 3, 2),
                (2, 100, 2, '35-39', 'F', 2, 4000, 40, 15.0, 5, 3),
                (3, 200, 3, '30-34', 'M', 1, 2000,  0,  0.0, 1, 0)
            ) t(ad_id, xyz_campaign_id, fb_campaign_id, age, gender, interest,
                Impressions, Clicks, Spent, Total_Conversion, Approved_Conversion)
        """)
        con.execute((paths.SQL / "kpis.sql").read_text())

    def test_rollup_sums_first(self, con):
        # campaign 100: ctr = 50/5000 = .01, cpc = 20/50 = .4, cpa = 20/5 = 4
        r = con.execute(
            "SELECT ctr, cpc, cpa FROM campaign_rollup WHERE campaign_id=100"
        ).fetchone()
        assert r[0] == pytest.approx(0.01)
        assert r[1] == pytest.approx(0.4)
        assert r[2] == pytest.approx(4.0)

    def test_rollup_is_not_average_of_ratios(self, con):
        # mean of ad CTRs would be (.01+.01)/2 = .01: here equal, so use CPA:
        # ad CPAs are 2.5 and 5.0, mean 3.75; the honest rollup is 4.0
        r = con.execute("SELECT cpa FROM campaign_rollup WHERE campaign_id=100").fetchone()
        assert r[0] != pytest.approx(3.75)

    def test_zero_guards_are_null_not_zero(self, con):
        r = con.execute("SELECT cpc, cpa FROM ad_kpis WHERE ad_id=3").fetchone()
        assert r[0] is None and r[1] is None

    def test_rank_within_campaign(self, con):
        rows = con.execute("""
            SELECT ad_id, cpa_rank FROM ad_rank_in_campaign
            WHERE campaign_id=100 ORDER BY cpa_rank
        """).fetchall()
        assert rows[0] == (1, 1)   # CPA 2.5 ranks best
        assert rows[1] == (2, 2)

    def test_running_spend(self, con):
        rows = con.execute("""
            SELECT ad_id, cumulative_spend FROM running_spend
            WHERE campaign_id=100 ORDER BY ad_id
        """).fetchall()
        assert rows[0][1] == pytest.approx(5.0)
        assert rows[1][1] == pytest.approx(20.0)


class TestEcommerceSql:
    @pytest.fixture(autouse=True)
    def setup(self, con):
        con.execute("""
            CREATE TABLE orders AS SELECT * FROM (VALUES
                ('o1','c1','delivered', TIMESTAMP '2018-01-01 10:00',
                 TIMESTAMP '2018-01-05 10:00', TIMESTAMP '2018-01-10 00:00'),
                ('o2','c2','delivered', TIMESTAMP '2018-01-02 10:00',
                 TIMESTAMP '2018-01-12 10:00', TIMESTAMP '2018-01-08 00:00'),
                ('o3','c3','canceled',  TIMESTAMP '2018-01-03 10:00',
                 NULL, TIMESTAMP '2018-01-09 00:00')
            ) t(order_id, customer_id, order_status, order_purchase_timestamp,
                order_delivered_customer_date, order_estimated_delivery_date)
        """)
        con.execute("""
            CREATE TABLE items AS SELECT * FROM (VALUES
                ('o1', 1, 'p1', 's1', 10.0, 2.0),
                ('o1', 2, 'p2', 's1', 20.0, 3.0),
                ('o2', 1, 'p1', 's2', 50.0, 5.0),
                ('o3', 1, 'p2', 's1',  5.0, 1.0)
            ) t(order_id, order_item_id, product_id, seller_id, price, freight_value)
        """)
        con.execute("""
            CREATE TABLE payments AS SELECT * FROM (VALUES
                ('o1', 1, 'card', 20.0), ('o1', 2, 'voucher', 15.0), ('o2', 1, 'card', 55.0)
            ) t(order_id, payment_sequential, payment_type, payment_value)
        """)
        con.execute("""
            CREATE TABLE reviews AS SELECT * FROM (VALUES
                ('r1','o1',5), ('r2','o2',1), ('r3','o2',2)  -- o2 reviewed twice
            ) t(review_id, order_id, review_score)
        """)
        con.execute("CREATE TABLE sellers AS SELECT 's1' seller_id, 'SP' seller_state UNION ALL SELECT 's2','RJ'")
        con.execute("CREATE TABLE customers AS SELECT 'c1' customer_id")
        con.execute("CREATE TABLE products AS SELECT 'p1' product_id, 'cat' product_category_name UNION ALL SELECT 'p2','cat'")
        con.execute("CREATE TABLE category_translation AS SELECT 'cat' product_category_name, 'cat_en' product_category_name_english")
        con.execute((paths.SQL / "ecommerce.sql").read_text())

    def test_order_facts_one_row_per_delivered_order(self, con):
        rows = con.execute("SELECT order_id, revenue FROM order_facts ORDER BY order_id").fetchall()
        assert rows == [("o1", 30.0), ("o2", 50.0)]  # o3 canceled; o1 = 10+20

    def test_review_deduped_before_join(self, con):
        r = con.execute("SELECT review_score FROM order_facts WHERE order_id='o2'").fetchone()
        assert r[0] == pytest.approx(1.5)  # avg of the two reviews, not two rows

    def test_late_flag_and_days(self, con):
        rows = dict(con.execute("SELECT order_id, days_late FROM order_facts").fetchall())
        assert rows["o1"] < 0          # early
        assert rows["o2"] == 4         # 4 days past the estimate
        late = dict(con.execute("SELECT order_id, is_late FROM order_facts").fetchall())
        assert late == {"o1": False, "o2": True}

    def test_join_trap_is_demonstrated(self, con):
        r = con.execute("SELECT honest_revenue, inflated_revenue FROM join_trap_check").fetchone()
        assert r[0] == pytest.approx(85.0)       # all items: 10+20+50+5
        # o1 has 2 payments x 2 items -> its 30 counts twice; o2 once; o3 unpaid absent
        assert r[1] == pytest.approx(30.0 * 2 + 50.0)
        assert r[1] > r[0]

    def test_delay_buckets(self, con):
        rows = dict(con.execute(
            "SELECT delay_bucket, orders FROM delay_vs_review").fetchall())
        assert rows == {"1. on time": 1, "3. >3 days late": 1}
