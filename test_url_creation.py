import unittest
from agents.task_planner import TaskPlanner
from router.task_router import TaskRouter
from models.strategy_models import DirectURLStrategy, RegistryStrategy, LLMStrategy

class TestURLCreation(unittest.TestCase):
    def setUp(self):
        self.planner = TaskPlanner()
        self.router = TaskRouter()

    def _route(self, query: str, clarification=None):
        plan = self.planner.plan(query, clarification)
        return self.router.route_task(query, plan)

    def test_example_a_amazon_search(self):
        query = "Search iPhone 16 on Amazon."
        # simulate user picking India
        strategy = self._route(query, clarification="Amazon India (INR)")
        self.assertIsInstance(strategy, DirectURLStrategy)
        self.assertEqual(strategy.url, "https://www.amazon.in/s?k=iPhone%2016")

    def test_example_a_amazon_us_search(self):
        query = "Search iPhone 16 on Amazon US."
        strategy = self._route(query)
        self.assertIsInstance(strategy, DirectURLStrategy)
        self.assertEqual(strategy.url, "https://www.amazon.com/s?k=iPhone%2016")

    def test_example_b_amazon_search(self):
        query = "Search iPhone 15 on Amazon."
        strategy = self._route(query, clarification="Amazon India (INR)")
        self.assertIsInstance(strategy, DirectURLStrategy)
        self.assertEqual(strategy.url, "https://www.amazon.in/s?k=iPhone%2015")

    def test_example_c_compare(self):
        query = "Compare iPhone 15 and iPhone 16 on Amazon."
        strategy = self._route(query, clarification="Amazon India (INR)")
        self.assertIsInstance(strategy, DirectURLStrategy)
        self.assertEqual(strategy.url, "https://www.amazon.in/s?k=iPhone%2015%20and%20iPhone%2016")

    def test_example_d_flipkart(self):
        query = "Search shoes on Flipkart."
        strategy = self._route(query)
        self.assertIsInstance(strategy, DirectURLStrategy)
        self.assertEqual(strategy.url, "https://www.flipkart.com/search?q=shoes")

    def test_unknown_website(self):
        query = "Go to books.toscrape.com and extract the price of a light in the attic"
        strategy = self._route(query)
        self.assertIsInstance(strategy, LLMStrategy)

if __name__ == "__main__":
    unittest.main()

