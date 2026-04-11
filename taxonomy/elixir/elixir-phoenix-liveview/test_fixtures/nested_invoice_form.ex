# fixture: attempted nested invoice form with broken inputs_for wiring
defmodule MyAppWeb.InvoiceLive.Edit do
  use MyAppWeb, :live_view

  alias MyApp.Billing
  alias MyApp.Billing.Invoice

  def mount(%{"id" => id}, _session, socket) do
    invoice = Billing.get_invoice!(id)
    changeset = Billing.change_invoice(invoice)

    socket =
      socket
      |> assign(:invoice, invoice)
      |> assign(:changeset, changeset)

    {:ok, socket}
  end

  def render(assigns) do
    ~H"""
    <.form :let={f} for={@changeset} phx-change="validate" phx-submit="save">
      <label>Customer</label>
      <%= text_input(f, :customer_name) %>

      <h3>Line items</h3>
      <%= for li <- inputs_for(f, :line_items) do %>
        <div class="line-item">
          <%= text_input(li, :description) %>
          <%= number_input(li, :amount) %>
        </div>
      <% end %>

      <button type="button" phx-click="add_line">Add line</button>
      <button type="submit">Save</button>
    </.form>
    """
  end

  def handle_event("validate", %{"invoice" => params}, socket) do
    changeset =
      socket.assigns.invoice
      |> Billing.change_invoice(params)

    {:noreply, assign(socket, :changeset, changeset)}
  end

  def handle_event("add_line", _params, socket) do
    existing = Ecto.Changeset.get_field(socket.assigns.changeset, :line_items) || []
    new_line = %MyApp.Billing.LineItem{}

    changeset =
      socket.assigns.changeset
      |> Ecto.Changeset.put_assoc(:line_items, existing ++ [new_line])

    {:noreply, assign(socket, :changeset, changeset)}
  end

  def handle_event("save", %{"invoice" => params}, socket) do
    case Billing.update_invoice(socket.assigns.invoice, params) do
      {:ok, invoice} -> {:noreply, assign(socket, invoice: invoice)}
      {:error, changeset} -> {:noreply, assign(socket, :changeset, changeset)}
    end
  end
end
