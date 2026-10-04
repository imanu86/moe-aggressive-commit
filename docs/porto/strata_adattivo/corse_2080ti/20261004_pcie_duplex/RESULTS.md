# PCIe full-duplex sulla 2080 Ti

`pcie_duplex.cu` (nvcc 12.6, sm_75): buffer host bloccati, 256 MiB per direzione, mediana di 8.
RTX 2080 Ti (bus 10:0), asyncEngineCount 2, PCIe 3.0 x16, macchina in uso (CGControl acceso).

| | H2D | D2H |
|---|---:|---:|
| da sola | 13,11 GB/s | 13,19 GB/s |
| insieme (due stream) | 11,51 GB/s | 11,33 GB/s |

Aggregato in contemporanea 22,67 GB/s: due motori di copia indipendenti, ciascuna direzione
perde circa il 12% quando l'altra e' attiva. Una RAM esclusiva con retrocessioni VRAM->RAM
non dimezza i caricamenti RAM->VRAM.
