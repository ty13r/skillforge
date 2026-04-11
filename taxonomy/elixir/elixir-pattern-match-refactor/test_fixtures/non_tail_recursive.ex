# fixture: Functions that use recursion but are non-tail or use list ++ [x].
defmodule MyApp.ListUtils do
  def doubled(list) do
    if list == [] do
      []
    else
      [head | tail] = list
      [head * 2] ++ doubled(tail)
    end
  end

  def running_sum([]), do: []

  def running_sum([head | tail]) do
    result = running_sum(tail)
    case result do
      [] -> [head]
      [prev | _] = rest -> [head + prev] ++ rest
    end
  end

  def build_path(segments) do
    path = ""

    for segment <- segments do
      path = path <> "/" <> segment
    end

    path
  end

  def collect_evens(list) do
    acc = []

    Enum.each(list, fn x ->
      if rem(x, 2) == 0 do
        acc = acc ++ [x]
      end
    end)

    acc
  end
end
