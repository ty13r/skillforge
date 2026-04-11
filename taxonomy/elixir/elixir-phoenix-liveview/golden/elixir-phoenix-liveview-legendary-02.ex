# golden: nested invoice form with <.inputs_for>, cast_assoc, sort_param/drop_param,
# add/remove buttons positioned AFTER the inputs_for list
defmodule MyAppWeb.InvoiceLive.Edit do
  use MyAppWeb, :live_view

  alias MyApp.Billing
  alias MyApp.Billing.Invoice

  def mount(%{"id" => id}, _session, socket) do
    invoice = Billing.get_invoice!(id)
    form = Billing.change_invoice(invoice) |> to_form()

    socket =
      socket
      |> assign(:invoice, invoice)
      |> assign(:form, form)

    {:ok, socket}
  end

  def render(assigns) do
    ~H"""
    <.form for={@form} phx-change="validate" phx-submit="save">
      <.input field={@form[:customer_name]} label="Customer" />

      <h3>Line items</h3>
      <.inputs_for :let={li} field={@form[:line_items]}>
        <input type="hidden" name="invoice[line_items_sort][]" value={li.index} />
        <.input field={li[:description]} label="Description" />
        <.input field={li[:amount]} type="number" label="Amount" />
        <button
          type="button"
          name="invoice[line_items_drop][]"
          value={li.index}
          phx-click={JS.dispatch("change")}
        >
          Remove
        </button>
      </.inputs_for>

      <input type="hidden" name="invoice[line_items_drop][]" />
      <button type="button" name="invoice[line_items_sort][]" value="new">
        Add line
      </button>

      <button type="submit">Save</button>
    </.form>
    """
  end

  def handle_event("validate", %{"invoice" => params}, socket) do
    form =
      socket.assigns.invoice
      |> Billing.change_invoice(params)
      |> Map.put(:action, :validate)
      |> to_form()

    {:noreply, assign(socket, :form, form)}
  end

  def handle_event("save", %{"invoice" => params}, socket) do
    case Billing.update_invoice(socket.assigns.invoice, params) do
      {:ok, invoice} ->
        {:noreply,
         socket
         |> put_flash(:info, "Saved")
         |> assign(:invoice, invoice)
         |> assign(:form, Billing.change_invoice(invoice) |> to_form())}

      {:error, changeset} ->
        {:noreply, assign(socket, :form, to_form(changeset))}
    end
  end
end
