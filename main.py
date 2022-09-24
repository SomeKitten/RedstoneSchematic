from __future__ import annotations

import circuitgraph
import mcschematic
import circuitgraph as cg
from logic_schematics import LogicSchematics

input_verilog = "test"

# change this dir to yur own schematic folder
output_dir = "/home/kitten/.local/share/multimc/instances/1.17.1/.minecraft/config/worldedit/schematics"

schem = mcschematic.MCSchematic()

circuit_from_verilog = cg.from_file(f"./verilog/{input_verilog}.v")


def recursive_process(circuit: circuitgraph.Circuit, depth_nodes: list, nodes: [str], depth: int):
    if depth >= len(depth_nodes):
        depth_nodes += [[], []]

    for node in nodes:
        if node not in map(lambda x: x[1], depth_nodes[depth]):
            if circuit.is_output(node):
                depth_nodes[depth] = [(circuit.type(node), node, [])] + depth_nodes[depth]
            else:
                depth_nodes[depth] += [(circuit.type(node), node, [])]
            fan = circuit.fanout(node)
            if len(fan) > 0:
                recursive_process(circuit, depth_nodes, fan, depth + 2)


def output_generation(circuit: circuitgraph.Circuit, depth_nodes: list):
    for depth in range(int(len(depth_nodes) / 2)):
        index = depth * 2 + 1

        before_len = len(depth_nodes[index - 1])
        after_len = len(depth_nodes[index + 1]) if index + 1 < len(depth_nodes) else 0
        depth_nodes[index] = []
        for i in range(max(before_len, after_len)):
            depth_nodes[index] += [("wire", "", [])]

        for i, node in enumerate(depth_nodes[index - 1]):
            typ, name, data = node

            if typ == "wire":
                continue
            if circuit.is_output(name):
                depth_nodes[index][i] = ("output", "", [])
                if after_len >= before_len:
                    depth_nodes[index] += [("wire", "", [])]
                shift_right(depth_nodes, index + 1)


# generate redstone wires
def wire_generation(circuit: circuitgraph.Circuit, depth_nodes: list):
    node_input_amount = {}
    for depth in range(int(len(depth_nodes) / 2)):
        index = depth * 2
        input_amount = 0

        if len(depth_nodes) <= index + 2:
            continue

        next_nodes = list(map(lambda x: x[1], depth_nodes[index + 2]))
        for i, node in enumerate(depth_nodes[index]):
            typ, name, data = node
            wire_node = depth_nodes[index + 1][i]

            fanout = circuit.fanout(name)
            for next_node in fanout:
                if next_node not in node_input_amount:
                    node_input_amount[next_node] = 0
                if node_input_amount[next_node] >= 2:
                    raise IndexError("Too many inputs")

                next_index = next_nodes.index(next_node)
                single_wire_generation(wire_node, next_index, "right" if node_input_amount[next_node] == 1 else "left",
                                       input_amount, i)
                node_input_amount[next_node] += 1
            if len(fanout) > 0:
                input_amount += 1


def single_wire_generation(node: tuple[str, str, list], next_index: int,
                           output_slot: str, input_amount: int, index: int):
    typ, name, data = node

    path = []

    path.append(("right", 2))

    path.append(("up", input_amount * 2))
    path.append(("forward", 2))

    right_amount = -4 + (next_index - index) * 5
    if output_slot == "right":
        right_amount += 3
    path.append(("right", right_amount))

    path.append(("forward", 2))

    path.append(("down_" + ("a" if output_slot == "left" else "b"), input_amount * 2))

    data.append(path)


def shift_right(depth_nodes: list, layer_from: int):
    for i in range(layer_from, len(depth_nodes)):
        depth_nodes[i] = [("wire", "", [])] + depth_nodes[i]


def create_wire(location: tuple[int, int, int], path: list[tuple[str, int | tuple[int, int, int]]]):
    x, y, z = location
    for direction, length in path:
        if direction == "offset":
            x += length[0]
            y += length[1]
            z += length[2]
            continue

        place_redstone((x, y, z))
        if length == 0:
            continue
        # reverse direction if negative
        if length < 0:
            direction = {
                "up": "down", "down": "up",
                "left": "right", "right": "left",
                "forward": "backward", "backward": "forward"
            }[direction]
            length = -length

        distance = 0
        first_placed = False

        if direction == "up":
            # generate glass ladder
            for _ in range(int(length)):
                if distance % 2 == 0:
                    schem.getStructure().placeStructure(LogicSchematics.wire_stair, (x, y, z))
                else:
                    schem.getStructure().placeStructure(LogicSchematics.wire_stair_flipped, (x, y, z))

                distance += 1
                y += 1
        elif direction.startswith("down"):
            # generate concrete staircase

            start_y = y
            for _ in range(int(length / 2)):
                y -= 2

                if direction == "down_a":
                    if distance % 4 == 2:
                        schem.getStructure().placeStructure(LogicSchematics.wire_stair_down_flipped,
                                                            (x - 1, start_y - (length - distance), z))
                    else:
                        schem.getStructure().placeStructure(LogicSchematics.wire_stair_down,
                                                            (x - 1, start_y - (length - distance), z + 1))
                if direction == "down_b":
                    if distance % 4 == 0:
                        schem.getStructure().placeStructure(LogicSchematics.wire_stair_down_flipped,
                                                            (x - 1, start_y - (length - distance), z))
                    else:
                        schem.getStructure().placeStructure(LogicSchematics.wire_stair_down,
                                                            (x - 1, start_y - (length - distance), z - 1))

                distance += 2

            if direction == "down_a":
                place_redstone((x - 1, y, z))

        elif direction == "forward":
            for _ in range(length):
                x += 1
                distance += 1

                first_placed = place_redstone((x, y, z), "west", first_placed and 0 < distance < length)
        elif direction == "backward":
            for _ in range(length):
                x -= 1
                distance += 1

                first_placed = place_redstone((x, y, z), "east", first_placed and 0 < distance < length)
        elif direction == "left":
            for _ in range(length):
                z -= 1
                distance += 1

                first_placed = place_redstone((x, y, z), "south", first_placed and 0 < distance < length)
        elif direction == "right":
            for _ in range(length):
                z += 1
                distance += 1

                first_placed = place_redstone((x, y, z), "north", first_placed and 0 < distance < length)
        else:
            raise ValueError(f"Unknown direction: {direction}")
        place_redstone((x, y, z))


AIR = "minecraft:air"
REDSTONE_WIRE = "minecraft:redstone_wire"
REDSTONE_REPEATER = "minecraft:repeater"
WHITE_CONCRETE = "minecraft:white_concrete"
WHITE_STAINED_GLASS = "minecraft:white_stained_glass"


def place_redstone(location: tuple[int, int, int], direction: str = "",
                   repeater: bool = False, glass: bool = False) -> bool:
    repeater_str = f"{REDSTONE_REPEATER}[facing={direction}]"

    if not (schem.getBlockStateAt(location) == AIR or is_redstone_component(location)) or \
            is_redstone_component((location[0], location[1] - 1, location[2])):
        return is_redstone_component(location)
    if is_redstone_component(location) and not is_facing(location, direction):
        repeater = False
    schem.setBlock(location, repeater_str if repeater else REDSTONE_WIRE)

    if schem.getBlockStateAt((location[0], location[1] - 1, location[2])) != AIR:
        return True
    schem.setBlock((location[0], location[1] - 1, location[2]), WHITE_STAINED_GLASS)  # if glass else WHITE_CONCRETE)

    return True


def is_redstone_component(location: tuple[int, int, int]):
    return any(map(lambda component: component in schem.getBlockStateAt(location), (REDSTONE_WIRE, REDSTONE_REPEATER)))


def is_facing(location: tuple[int, int, int], direction: str):
    return f"facing={direction}" in schem.getBlockStateAt(location)


def main(circuit):
    print(f"is cyclic: {circuit.is_cyclic()}")

    depth_nodes = []
    recursive_process(circuit, depth_nodes, circuit.inputs(), 0)
    output_generation(circuit, depth_nodes)
    wire_generation(circuit, depth_nodes)

    for depth, nodes in enumerate(depth_nodes):
        print(f"Depth {depth}: {len(nodes)}")

        up = depth * 5

        for index, node in enumerate(nodes):
            typ, name, data = node

            print(f"    {name}: {typ}")
            for d in data:
                print(f"        {d}")

            right = index * 5

            if typ in LogicSchematics.nodes:
                schem.placeSchematic(LogicSchematics.nodes[typ], (up, 0, right))
                if len(data) > 0:
                    for path in data:
                        create_wire((up, 1, right + 2), path)

    schem.save(output_dir, "logic", mcschematic.Version.JE_1_17_1)


main(circuit_from_verilog)
