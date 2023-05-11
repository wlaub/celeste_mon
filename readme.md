
`main.py`
dumps timestamp raw game state info into the binary file `<timestamp>.dat`. Terminate with a keyboard interrupt. Something like 50 or so MB per hour of in-map duration (chapter select doesn't tend to generate new states).

When a state takes longer than 1/60 of a second (i.e. 1 frame at 60 fps) to change, the script prints the duration in frames. Typically this is due to a respawn or menu transition.

`decode.py <data file> [room name] [room name] ...`
loads the data file, chunks by room, splits up rooms into 'runs' (sequences of states ending in death, room change, or an unhandled msg), and logs some metadata about the rooms to `<data file>_index.json`. Then if room names are given, it plots the runs from named rooms. If no rooms are given, it just lists the available rooms and their combined run counts.

Example output:
```
$ python -u decode.py twm-2023-05-10-142030.dat c-b1
c-01: 3 runs
c-02: 3 runs
c-03: 21 runs
c-04: 12 runs
c-b1: 36 runs
c-06: 32 runs
c-07: 8 runs
e-x1: 1 runs
e-02: 15 runs
b-x4: 1 runs
b-03: 2 runs
b-05: 26 runs
b-04: 1 runs
b-06: 3 runs
b-07: 4 runs
b-08: 7 runs
b-01: 2 runs
f-01: 2 runs
b-02: 2 runs
c-g1: 1 runs
c-g2: 2 runs
c-g3: 24 runs
c-g4: 13 runs
c-g5: 1 runs
c-g6: 40 runs
c-b2: 15 runs
c-05: 4 runs
```

Example: 40 runs of a hidden berry room from the wednesday machine

![image](example_twm-c-b1.png)

black dots are positions in a run that ends in a death
red x's are deaths
magenta dots are positions not ending in a death (including ending in a watchtower, for example)
large blue dots are the starts of runs (respawn or room transition)
the grid size is 8 pixels (1 in-game tile)
