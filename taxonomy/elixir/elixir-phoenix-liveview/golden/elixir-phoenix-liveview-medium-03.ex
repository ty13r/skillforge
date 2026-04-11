# golden: contact form wired with to_form/2, action: :validate, and used_input?/1
defmodule MyAppWeb.ContactLive do
  use MyAppWeb, :live_view

  alias MyApp.Support
  alias MyApp.Support.ContactRequest

  def mount(_params, _session, socket) do
    form = Support.change_contact(%ContactRequest{}) |> to_form()
    {:ok, assign(socket, :form, form)}
  end

  def render(assigns) do
    ~H"""
    <div>
      <h1>Contact us</h1>
      <.form for={@form} phx-change="validate" phx-submit="save">
        <.input field={@form[:name]} label="Name" />
        <.input field={@form[:email]} type="email" label="Email" />
        <.input field={@form[:message]} type="textarea" label="Message" />
        <button type="submit">Send</button>
      </.form>
    </div>
    """
  end

  def handle_event("validate", %{"contact_request" => params}, socket) do
    form =
      %ContactRequest{}
      |> Support.change_contact(params)
      |> Map.put(:action, :validate)
      |> to_form()

    {:noreply, assign(socket, :form, form)}
  end

  def handle_event("save", %{"contact_request" => params}, socket) do
    case Support.create_contact(params) do
      {:ok, _request} ->
        {:noreply,
         socket
         |> put_flash(:info, "Sent")
         |> push_navigate(to: ~p"/")}

      {:error, changeset} ->
        {:noreply, assign(socket, :form, to_form(changeset))}
    end
  end
end
