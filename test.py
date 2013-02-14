from fabric.main import load_fabfile

import unittest

class TestFabness(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_fab_task_generation(self):
        ''' Load the fabfile with test data and see if `deploy` task is created. '''
        docstring, tasks, default = load_fabfile('fabfile.py')
        self.assertIn('deploy', tasks)


if __name__ == '__main__':
    unittest.main()
