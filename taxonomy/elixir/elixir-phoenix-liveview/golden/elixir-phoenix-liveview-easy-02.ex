# golden: HEEx :for attribute replacing the legacy EEx list comprehension form
defmodule MyAppWeb.SimpleListLive do
  use MyAppWeb, :live_view

  def mount(_params, _session, socket) do
    {:ok, assign(socket, :items, ["apple", "banana", "cherry"])}
  end

  def render(assigns) do
    ~H"""
    <ul>
      <li :for={item <- @items}>{item}</li>
    </ul>
    """
  end
end
