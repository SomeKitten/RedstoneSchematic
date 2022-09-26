from __future__ import annotations

import subprocess
import time

import circuitgraph
import mcschematic
import circuitgraph as cg
from logic_schematics import LogicSchematics

time_str = time.strftime("%Y-%m-%d--%H:%M:%S")

# change this dir to your own schematic folder
output_dir = "/home/kitten/.local/share/multimc/instances/1.17.1/.minecraft/config/worldedit/schematics"
dump_file_path = f"./generated/{time_str}_dump"

schem = mcschematic.MCSchematic()

circuit_type = "mux"

if circuit_type == "mux":
    circuit_from_verilog = cg.logic.mux(3)
elif circuit_type == "full_adder":
    circuit_from_verilog = cg.logic.full_adder()
else:
    circuit_from_verilog = cg.Circuit()
# else:
# circuit_from_verilog = cg.tx.syn(cg.Circuit(), verilog_exists=True, pre_syn_file=f"./verilog/{circuit_type}.v",
#                                  post_syn_file=f"./verilog/{circuit_type}_syn.v", suppress_output=True)

cg.to_file(circuit_from_verilog, f"{dump_file_path}.v")
syn_command = [
    "yosys",
    "-p",
    f"read_verilog {dump_file_path}.v; "
    "splitnets -ports; "
    f"write_verilog -noattr {dump_file_path}_syn.v; "
]

yosys_subprocess_result = subprocess.run(syn_command, capture_output=True, text=True)
# uncomment lines below for yosys output
# print(yosys_subprocess_result.stdout)
# print(yosys_subprocess_result.stderr)

circuit_from_verilog = cg.from_file(f"{dump_file_path}_syn.v")

cg.visualize(circuit_from_verilog, f"generated/{time_str}_{circuit_type}.png")
cg.to_file(circuit_from_verilog, f"generated/{time_str}_{circuit_type}.v")


class Node:
    def __init__(self, typ: str, name: str, data: list[list[tuple[str, int | tuple[int, int, int]]]],
                 output: set[str]):
        self.typ = typ
        self.name = name
        self.data = data
        self.output = output

    def to_tuple(self):
        return self.typ, self.name, self.data, self.output

    def __repr__(self):
        return f"Node({self.typ}, {self.name}, {self.data}, {self.output})"


def nodes_to_names(nodes: list[Node]):
    return [node.name for node in nodes]


def recursive_process(circuit: circuitgraph.Circuit, depth_nodes: list[list[Node]], nodes: [str], depth: int):
    if depth >= len(depth_nodes):
        depth_nodes += [[], []]

    for node in nodes:
        if node not in nodes_to_names(depth_nodes[depth]):
            fan = circuit.fanout(node)
            if circuit.is_output(node):
                if len(fan) > 0:
                    print(f"Warning: output {node} has fanout {fan}")
                depth_nodes[depth] = [Node(circuit.type(node), node, [], set())] + depth_nodes[depth]
            elif len(fan) > 0:
                depth_nodes[depth] += [Node(circuit.type(node), node, [], fan)]
                recursive_process(circuit, depth_nodes, fan, depth + 2)
            else:
                print(f"Warning: {node} - {circuit.type(node)} has no fanout")
                circuit.set_output(node)
                depth_nodes[depth] = [Node(circuit.type(node), node, [], set())] + depth_nodes[depth]


def redundant_node_deletion(depth_nodes: list[list[Node]]):
    s = set()
    for index, layer in enumerate(reversed(depth_nodes)):
        index = len(depth_nodes) - index - 1
        depth_nodes[index] = [node for node in layer if node.name not in s]
        s |= set(nodes_to_names(layer))


def wide_gate_splitter(depth_nodes: list[list[Node]]):
    node_input_amount = {}
    index = 0
    while index < len(depth_nodes):
        current_layer = depth_nodes[index]
        for i, node in enumerate(current_layer):
            typ, name, data, output = node.to_tuple()
            if typ == "buf":
                continue

            for out in output.copy():
                if out not in node_input_amount:
                    node_input_amount[out] = 0

                node_input_amount[out] += 1

                if node_input_amount[out] > 2:
                    print(f"{out} has {node_input_amount[out]} inputs")

                    out_node, out_index = get_node(depth_nodes, out)
                    next_node = Node(out_node.typ, f"{out}_ext_{node_input_amount[out] - 3}", [], out_node.output)
                    out_node.output = {next_node.name}
                    output.remove(out)
                    output.add(next_node.name)

                    new_layer = [next_node]
                    for node_inner in current_layer:
                        if len(node_inner.output) == 0:
                            new_layer = [Node("wire", "", [], set())] + new_layer
                        else:
                            break

                    shift_right(depth_nodes, index + 2)

                    depth_nodes.insert(out_index + 1, new_layer)
                    depth_nodes.insert(out_index + 1, [])
        index += 2


def get_node(depth_nodes: list[list[Node]], name: str):
    for index, layer in enumerate(depth_nodes):
        for node in layer:
            if node.name == name:
                return node, index
    raise KeyError(f"Node {name} not found")


def get_node_from_layer(layer: list[Node], name: str):
    for node in layer:
        if node.name == name:
            return node
    raise KeyError(f"Node {name} not found")


def tunnel_generation(depth_nodes: list[list[Node]]):
    tunnel_amount = 0

    for depth in range(len(depth_nodes) // 2 - 1):
        index = depth * 2
        nodes = depth_nodes[index]
        next_nodes = depth_nodes[index + 2]
        next_nodes_names = nodes_to_names(next_nodes)

        for i, node in enumerate(nodes):
            typ, name, data, output = node.to_tuple()

            tunnel_outputs = []
            for out in output:
                if out not in next_nodes_names:
                    tunnel_outputs.append(out)
            output -= set(tunnel_outputs)

            if len(tunnel_outputs) > 0:
                tunnel_name = f"tunnel{tunnel_amount}"
                next_nodes += [Node("buf", tunnel_name, [], set(tunnel_outputs))]
                output.add(tunnel_name)
                tunnel_amount += 1


def inbetween_generation(depth_nodes: list[list[Node]]):
    for depth in range(len(depth_nodes) // 2):
        index = depth * 2 + 1

        before_len = len(depth_nodes[index - 1])
        after_len = len(depth_nodes[index + 1]) if index + 1 < len(depth_nodes) else 0
        depth_nodes[index] = []
        for _ in range(max(before_len, after_len)):
            depth_nodes[index] += [Node("wire", "", [], set())]


def output_generation(depth_nodes: list[list[Node]]):
    for depth in range(len(depth_nodes) // 2):
        index = depth * 2 + 1

        before_len = len(depth_nodes[index - 1])
        after_len = len(depth_nodes[index + 1]) if index + 1 < len(depth_nodes) else 0

        for i, node in enumerate(depth_nodes[index - 1]):
            typ, name, data, output = node.to_tuple()

            if typ == "wire" or typ == "blank" or len(output) > 0:
                continue

            depth_nodes[index][i] = Node("output", f"Output: {name}", [], set())
            if after_len >= before_len:
                depth_nodes[index] += [Node("wire", "", [], set())]
            shift_right(depth_nodes, index + 1)


def get_input_amount(depth_nodes: list[list[Node]]):
    node_input_amount = {}
    for depth in range(len(depth_nodes) // 2):
        index = depth * 2

        for i, node in enumerate(depth_nodes[index]):
            typ, name, data, output = node.to_tuple()

            for next_node in output:
                if next_node not in node_input_amount:
                    node_input_amount[next_node] = 0
                if node_input_amount[next_node] >= 2:
                    raise IndexError("Too many inputs")
                node_input_amount[next_node] += 1

    return node_input_amount


def reorganize_paths(depth_nodes: list[list[Node]], node_input_amount: dict[str, int]):
    for depth in range(len(depth_nodes) // 2 - 1):
        index = depth * 2

        for i, node in enumerate(depth_nodes[index]):
            typ, name, data, output = node.to_tuple()

            if len(output) != 1:
                continue

            only_output = list(output)[0]

            if only_output not in node_input_amount:
                print(f"Warning: Node {only_output} should have input, but has none!")
                continue

            if node_input_amount[only_output] > 1:
                continue

            next_index = index + 2
            next_node = get_node_from_layer(depth_nodes[next_index], only_output)

            if len(next_node.output) == 0:
                continue

            depth_nodes[next_index].remove(next_node)
            depth_nodes[next_index].insert(i, next_node)

            depth_nodes[index + 1][i] = Node("path", "", [], set())


def clear_path_rows(depth_nodes: list[list[Node]]):
    remove_rows = []
    for depth in range(len(depth_nodes) // 2 - 1):
        index = depth * 2 + 1

        if all((node.typ == "path" or node.typ == "blank") for node in depth_nodes[index]):
            remove_rows.insert(0, index)

    for index in remove_rows:
        print(f"Removing row {[node.typ for node in depth_nodes[index]]}")
        depth_nodes.pop(index)
        print(f"Removing row {[node.typ for node in depth_nodes[index]]}")
        removed_row = depth_nodes.pop(index)

        for node_index, node in enumerate(depth_nodes[index - 1]):
            node.output = removed_row[node_index].output


# generate redstone wires
def wire_generation(depth_nodes: list[list[Node]]):
    node_input_amount = {}
    for depth in range(len(depth_nodes) // 2):
        index = depth * 2
        input_amount = 0

        if len(depth_nodes) <= index + 2:
            continue

        next_nodes = nodes_to_names(depth_nodes[index + 2])
        for i, node in enumerate(depth_nodes[index]):
            typ, name, data, output = node.to_tuple()
            wire_node = depth_nodes[index + 1][i]

            if wire_node.typ != "wire":
                continue

            for next_node in output:
                if next_node not in node_input_amount:
                    node_input_amount[next_node] = 0
                if node_input_amount[next_node] >= 2:
                    raise IndexError("Too many inputs")

                next_index = next_nodes.index(next_node)
                single_wire_generation(wire_node, next_index, "right" if node_input_amount[next_node] == 1 else "left",
                                       input_amount, i)
                node_input_amount[next_node] += 1
            if len(output) > 0:
                input_amount += 1


def single_wire_generation(node: Node, next_index: int,
                           output_slot: str, input_amount: int, index: int):
    typ, name, data, output = node.to_tuple()

    path = []

    height = input_amount * 2 + 2

    path.append(("right", 2))

    path.append(("up", height))
    path.append(("forward", 2))

    right_amount = -4 + (next_index - index) * 5
    if output_slot == "right":
        right_amount += 3
    path.append(("right", right_amount))

    path.append(("forward", 2))

    path.append(("down_" + ("a" if output_slot == "left" else "b"), height))

    data.append(path)


def shift_right(depth_nodes: list[list[Node]], layer_from: int):
    for i in range(layer_from, len(depth_nodes)):
        depth_nodes[i] = [Node("blank", "", [], set())] + depth_nodes[i]


def create_wire(location: tuple[int, int, int], path: list[tuple[str, int | tuple[int, int, int]]]):
    x, y, z = location
    for direction, length in path:
        if direction == "offset":
            x += length[0]
            y += length[1]
            z += length[2]
            continue

        distance = 0
        first_placed = place_redstone((x, y, z))

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

                first_placed |= place_redstone((x, y, z), "west", first_placed and 0 < distance < length)
        elif direction == "backward":
            for _ in range(length):
                x -= 1
                distance += 1

                first_placed |= place_redstone((x, y, z), "east", first_placed and 0 < distance < length)
        elif direction == "left":
            for _ in range(length):
                z -= 1
                distance += 1

                first_placed |= place_redstone((x, y, z), "south", first_placed and 0 < distance < length)
        elif direction == "right":
            for _ in range(length):
                z += 1
                distance += 1

                first_placed |= place_redstone((x, y, z), "north", first_placed and 0 < distance < length)
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


def main(circuit: circuitgraph.Circuit):
    print(f"is cyclic: {circuit.is_cyclic()}")

    depth_nodes: list[list[Node]] = []
    recursive_process(circuit, depth_nodes, circuit.inputs(), 0)
    redundant_node_deletion(depth_nodes)
    wide_gate_splitter(depth_nodes)
    tunnel_generation(depth_nodes)
    inbetween_generation(depth_nodes)
    output_generation(depth_nodes)

    node_input_amount = get_input_amount(depth_nodes)
    reorganize_paths(depth_nodes, node_input_amount)

    clear_path_rows(depth_nodes)
    wire_generation(depth_nodes)

    for depth, nodes in enumerate(depth_nodes):
        print(f"Depth {depth}: {len(nodes)}")

        up = depth * 5

        for index, node in enumerate(nodes):
            typ, name, data, output = node.to_tuple()

            print(f"    {name} - {typ}: ")
            for d in data:
                print(f"        data:{d}")
            print(f"        output: {output}")

            right = index * 5

            if typ in LogicSchematics.nodes:
                schem.placeSchematic(LogicSchematics.nodes[typ], (up, 0, right))
                if len(data) > 0:
                    for path in data:
                        create_wire((up, 1, right + 2), path)

                sign_nbt = "minecraft:birch_sign[rotation=4]{Text1:'{\"text\":\"" + \
                           typ.replace("\\", "\\\\\\\\") + "\"}',Text2:'{\"text\":\"" + \
                           name.replace("\\", "\\\\\\\\") + "\"}'}"
                schem.setBlock((up, 3, right + 2), sign_nbt)

    schem.save(output_dir, "logic", mcschematic.Version.JE_1_17_1)


main(circuit_from_verilog)
