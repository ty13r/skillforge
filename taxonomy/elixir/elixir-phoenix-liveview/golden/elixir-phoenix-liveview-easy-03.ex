# golden: move a single Repo.all call from mount/3 to handle_params/3
defmodule MyAppWeb.CustomersLive do
  use MyAppWeb, :live_view

  alias MyApp.Sales

  def mount(_params, _session, socket) do
    {:ok, assign(socket, :customers, [])}
  end

  def handle_params(_params, _url, socket) do
    customers = Sales.list_customers()
    {:noreply, assign(socket, :customers, customers)}
  end

  def render(assigns) do
    ~H"""
    <ul>
      <li :for={c <- @customers}>{c.name}</li>
    </ul>
    """
  end
end
