.PHONY: test verify hpc-check report paper check
export PYTHONPATH := src

test:
	python3 -m unittest discover -s tests -v
verify:
	python3 formal/run_assurance.py $(if $(TLA2TOOLS_JAR),--tlc-jar "$(TLA2TOOLS_JAR)",)
hpc-check:
	bash hpc/scripts/selftest.sh
report:
	python3 experiments/scripts/update_report.py
paper: report
	bash paper/build.sh
check: test verify hpc-check
