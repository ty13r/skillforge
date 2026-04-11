# fixture: Manual loops that use list ++ [x] (O(n²)) instead of prepend-then-reverse.
defmodule MyApp.Collector do
  def chars_to_upper(string) do
    string
    |> String.graphemes()
    |> upper_loop([])
  end

  defp upper_loop([], acc), do: acc

  defp upper_loop([head | tail], acc) do
    upper_loop(tail, acc ++ [String.upcase(head)])
  end

  def numbered(list) do
    numbered_loop(list, 1, [])
  end

  defp numbered_loop([], _n, acc), do: acc

  defp numbered_loop([head | tail], n, acc) do
    numbered_loop(tail, n + 1, acc ++ [{n, head}])
  end

  def positive_only(list) do
    filter_loop(list, [])
  end

  defp filter_loop([], acc), do: acc

  defp filter_loop([head | tail], acc) when head > 0 do
    filter_loop(tail, acc ++ [head])
  end

  defp filter_loop([_head | tail], acc) do
    filter_loop(tail, acc)
  end
end
