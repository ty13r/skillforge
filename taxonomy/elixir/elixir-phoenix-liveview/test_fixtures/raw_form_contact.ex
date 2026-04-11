# fixture: form without to_form/2, missing action: :validate, manual changeset mutation
defmodule MyAppWeb.ContactLive do
  use MyAppWeb, :live_view

  alias MyApp.Support
  alias MyApp.Support.ContactRequest

  def mount(_params, _session, socket) do
    changeset = Support.change_contact(%ContactRequest{})
    {:ok, assign(socket, changeset: changeset)}
  end

  def render(assigns) do
    ~H"""
    <div>
      <h1>Contact us</h1>
      <.form :let={f} for={@changeset} phx-change="validate" phx-submit="save">
        <div>
          <label>Name</label>
          <%= text_input(f, :name) %>
          <%= error_tag(f, :name) %>
        </div>
        <div>
          <label>Email</label>
          <%= text_input(f, :email) %>
          <%= error_tag(f, :email) %>
        </div>
        <div>
          <label>Message</label>
          <%= textarea(f, :message) %>
          <%= error_tag(f, :message) %>
        </div>
        <button type="submit">Send</button>
      </.form>
    </div>
    """
  end

  def handle_event("validate", %{"contact_request" => params}, socket) do
    changeset = Support.change_contact(%ContactRequest{}, params)
    # ANTI-PATTERN: Map.put into changeset instead of using Ecto.Changeset API
    changeset = Map.put(changeset, :errors, changeset.errors)
    {:noreply, assign(socket, changeset: changeset)}
  end

  def handle_event("save", %{"contact_request" => params}, socket) do
    case Support.create_contact(params) do
      {:ok, _request} ->
        {:noreply, put_flash(socket, :info, "Sent")}

      {:error, changeset} ->
        {:noreply, assign(socket, changeset: changeset)}
    end
  end
end
