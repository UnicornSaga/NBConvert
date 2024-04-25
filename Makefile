.PHONY: test
test: test-unit

	@echo "\a"

.PHONY: test-unit
test-unit:
	@echo "----------------"
	@echo "- Unit Testing -"
	@echo "----------------"

	python -m unittest discover -s ./nbconvert/tests/ -p 'test_*.py'

	@echo ""

.PHONY: coverage
coverage:
	@echo "------------"
	@echo "- Coverage -"
	@echo "------------"

	coverage run -m unittest discover -s ./nbconvert/tests/ -p 'test_*.py'

	coverage run -m pytest ./nbconvert/tests/

	@echo ""

	coverage report -m