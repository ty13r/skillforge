defmodule MyApp.ListUtils do
  def doubled(list), do: do_doubled(list, [])

  defp do_doubled([], acc), do: Enum.reverse(acc)
  defp do_doubled([head | tail], acc), do: do_doubled(tail, [head * 2 | acc])

  def build_path(segments) do
    segments
    |> Enum.map(&("/" <> &1))
    |> Enum.join("")
  end

  def collect_evens(list) do
    list
    |> Enum.filter(&(rem(&1, 2) == 0))
  end
end
