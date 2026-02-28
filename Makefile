test_sma_crossover:
	docker run --rm \
		$$(docker build -q --target prod .) \
		"sma_crossover" "^990100-USD-STRD" "200" "20:00" "16:30" "America/New_York"
