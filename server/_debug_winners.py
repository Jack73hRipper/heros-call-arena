"""Quick debug script to check winner values from batch matches."""
import batch_pvpve

results = []
for i in range(3):
    r = batch_pvpve.run_headless_pvpve(grid_size=4, team_size=3, max_turns=100, seed=200+i, show_ascii=False)
    w = r["winner"]
    print(f"Match {i+1}: winner={w!r}")
    results.append(r)

batch_pvpve.print_batch_results(results)
