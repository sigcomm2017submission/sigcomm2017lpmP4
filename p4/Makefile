programs=$(patsubst %.p4, %.json, $(wildcard *.p4))

all : $(programs)

%.json : %.p4
	p4c-bmv2 --json $@ $< --primitives ../target/build/primitives.json
