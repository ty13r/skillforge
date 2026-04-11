# fixture: LiveView mixing push_redirect / live_patch / live_link — all deprecated in 1.7
defmodule MyAppWeb.OrdersLive do
  use MyAppWeb, :live_view

  alias MyApp.Orders

  def mount(_params, _session, socket) do
    {:ok, assign(socket, :orders, Orders.list_orders())}
  end

  def handle_params(%{"filter" => filter}, _url, socket) do
    orders = Orders.list_orders(filter)
    {:noreply, assign(socket, :orders, orders)}
  end

  def handle_params(_params, _url, socket) do
    {:noreply, socket}
  end

  def render(assigns) do
    ~L"""
    <div>
      <h1>Orders</h1>
      <nav>
        <%= live_patch "All", to: Routes.order_path(@socket, :index, filter: "all") %>
        <%= live_patch "Open", to: Routes.order_path(@socket, :index, filter: "open") %>
        <%= live_redirect "Archived", to: Routes.archived_order_path(@socket, :index) %>
      </nav>
      <ul>
        <%= for order <- @orders do %>
          <li>
            <%= live_link order.reference, to: Routes.order_path(@socket, :show, order) %>
          </li>
        <% end %>
      </ul>
    </div>
    """
  end

  def handle_event("new", _params, socket) do
    {:noreply, push_redirect(socket, to: Routes.order_path(socket, :new))}
  end

  def handle_event("filter", %{"value" => value}, socket) do
    {:noreply, push_patch(socket, to: Routes.order_path(socket, :index, filter: value))}
  end
end
