.PHONY: test
test: test-unit test-integration

	@echo "\a"

.PHONY: test-unit
test-unit:
	@echo "----------------"
	@echo "- Unit Testing -"
	@echo "----------------"

	python -m unittest discover -s ./nbconvert/tests/ -p 'test_*.py'

	@echo ""

.PHONY: test-integration
test-integration:
	@echo "-----------------------"
	@echo "- Integration Testing -"
	@echo "-----------------------"

	python -m unittest discover -s ./nbconvert/tests/ -p 'test_*.py'
	@echo ""

.PHONY: coverage
coverage:
	@echo "------------"
	@echo "- Coverage -"
	@echo "------------"

	coverage run -m unittest discover -s ./nbconvert/tests/ -p 'test_*.py'

	@echo ""

	coverage report -m