import mcschematic


class LogicSchematics:
    gate_and = mcschematic.MCSchematic("./schematics/and.schem")
    gate_nand = mcschematic.MCSchematic("./schematics/nand.schem")
    gate_nor = mcschematic.MCSchematic("./schematics/nor.schem")
    gate_not = mcschematic.MCSchematic("./schematics/not.schem")
    gate_or = mcschematic.MCSchematic("./schematics/or.schem")
    gate_xnor = mcschematic.MCSchematic("./schematics/xnor.schem")
    gate_xor = mcschematic.MCSchematic("./schematics/xor.schem")

    io_input = mcschematic.MCSchematic("./schematics/input.schem")
    io_output = mcschematic.MCSchematic("./schematics/output.schem")

    blank = mcschematic.MCSchematic("./schematics/blank.schem")

    nodes = {
        "and": gate_and,
        "nand": gate_nand,
        "nor": gate_nor,
        "not": gate_not,
        "or": gate_or,
        "xnor": gate_xnor,
        "xor": gate_xor,
        "input": io_input,
        "output": io_output,
        "wire": blank
    }

    wire_stair_up = mcschematic.MCSchematic("./schematics/stair_up.schem").getStructure()
    wire_stair_down = mcschematic.MCSchematic("./schematics/stair_down.schem").getStructure()
    wire_stair_down_flipped = wire_stair_down.makeCopy().flip((0, 0, 0), "yz").translate((1, 0, 0))
    wire_stair = mcschematic.MCSchematic("./schematics/stair.schem").getStructure()
    wire_stair_flipped = wire_stair.makeCopy().flip((0, 0, 0), "yz").translate((1, 0, 0))
