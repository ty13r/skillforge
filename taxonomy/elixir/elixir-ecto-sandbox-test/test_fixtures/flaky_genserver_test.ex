# fixture: Flaky test — GenServer started via start_link outlives the test process
defmodule MyApp.CounterServerTest do
  use MyApp.DataCase, async: true

  alias MyApp.CounterServer
  alias MyApp.Metrics

  test "increments a counter and records a metric" do
    # BUG: start_link creates a process unlinked from the test process.
    # When the test returns, the GenServer is still alive — and the sandbox
    # owner (the test process) has already relinquished the connection,
    # so the GenServer's next Repo call produces an ownership error that
    # manifests as "cannot find ownership process for #PID<...>".
    {:ok, pid} = CounterServer.start_link(name: :my_counter)

    CounterServer.increment(pid)
    CounterServer.increment(pid)

    # CounterServer writes a metric via Repo.insert — runs in the GenServer process,
    # which was never `allow/3`-ed.
    assert Metrics.total_increments() == 2
  end
end
