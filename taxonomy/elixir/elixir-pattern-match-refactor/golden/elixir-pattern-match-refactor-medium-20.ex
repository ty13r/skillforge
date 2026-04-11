defmodule MyApp.OrderFormatter do
  def summary(%{id: id, items: items, total: total}) do
    formatted =
      items
      |> Enum.map(fn %{name: name, quantity: qty} -> "#{qty}x #{name}" end)
      |> Enum.join(", ")

    "Order #{id}: #{formatted} — Total: $#{total}"
  end

  def summary(_), do: "Invalid order"

  def plot_point(%{x: x, y: y, z: z}), do: {x, y, z}
end
