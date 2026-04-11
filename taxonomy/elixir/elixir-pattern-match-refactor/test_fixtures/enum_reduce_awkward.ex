# fixture: Enum.reduce calls where the callback shape is awkward and explicit recursion
# would be clearer, OR explicit recursion where a simple Enum.map/filter is better.
defmodule MyApp.Accumulators do
  def group_by_parity(list) do
    Enum.reduce(list, %{evens: [], odds: []}, fn x, acc ->
      if rem(x, 2) == 0 do
        %{acc | evens: acc.evens ++ [x]}
      else
        %{acc | odds: acc.odds ++ [x]}
      end
    end)
  end

  def first_match([], _), do: nil

  def first_match([head | tail], predicate) do
    if predicate.(head) do
      head
    else
      first_match(tail, predicate)
    end
  end

  def doubled([]), do: []

  def doubled([head | tail]) do
    [head * 2 | doubled(tail)]
  end

  def max_value([]), do: nil

  def max_value([head | tail]) do
    case max_value(tail) do
      nil -> head
      other -> if head > other, do: head, else: other
    end
  end
end
