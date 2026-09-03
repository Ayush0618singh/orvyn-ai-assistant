"use client";

import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getAutoMemorySettings,
  updateAutoMemorySettings,
} from "@/services/autoMemoryService";

import {
  createMemory,
  deleteMemory,
  getMemories,
  updateMemory,
} from "@/services/memoryService";

import type {
  Memory,
  MemoryType,
} from "@/types/memory";


const MEMORY_TYPES: MemoryType[] = [
  "fact",
  "preference",
  "instruction",
  "note",
  "profile",
];


type TypeFilter =
  | MemoryType
  | "all";


type StatusFilter =
  | "all"
  | "active"
  | "inactive";


function formatMemoryType(
  type: MemoryType
): string {
  return (
    type.charAt(0).toUpperCase()
    + type.slice(1)
  );
}


function formatDate(
  value: string
): string {
  const date =
    new Date(value);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return "";
  }

  return date.toLocaleString();
}


function isMemoryType(
  value: string
): value is MemoryType {
  return MEMORY_TYPES.includes(
    value as MemoryType
  );
}


export default function MemoryManager() {
  const [
    memories,
    setMemories,
  ] = useState<Memory[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    saving,
    setSaving,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");

  const [
    successMessage,
    setSuccessMessage,
  ] = useState("");

  const [
    searchQuery,
    setSearchQuery,
  ] = useState("");

  const [
    typeFilter,
    setTypeFilter,
  ] = useState<TypeFilter>(
    "all"
  );

  const [
    statusFilter,
    setStatusFilter,
  ] = useState<StatusFilter>(
    "all"
  );

  const [
    editingMemory,
    setEditingMemory,
  ] = useState<Memory | null>(
    null
  );

  const [
    editContent,
    setEditContent,
  ] = useState("");

  const [
    editType,
    setEditType,
  ] = useState<MemoryType>(
    "fact"
  );

  const [
    editImportance,
    setEditImportance,
  ] = useState(0.5);

  const [
    newMemoryOpen,
    setNewMemoryOpen,
  ] = useState(false);

  const [
    newContent,
    setNewContent,
  ] = useState("");

  const [
    newType,
    setNewType,
  ] = useState<MemoryType>(
    "fact"
  );

  const [
    newImportance,
    setNewImportance,
  ] = useState(0.5);

  const [
    autoMemoryEnabled,
    setAutoMemoryEnabled,
  ] = useState(false);

  const [
    autoMemoryLoading,
    setAutoMemoryLoading,
  ] = useState(true);

  const [
    autoMemorySaving,
    setAutoMemorySaving,
  ] = useState(false);


  async function loadMemories() {
    setLoading(true);

    try {
      const data =
        await getMemories({
          activeOnly: false,
        });

      setMemories(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load memories."
      );
    } finally {
      setLoading(false);
    }
  }


  async function loadAutoMemorySettings() {
    setAutoMemoryLoading(true);

    try {
      const settings =
        await getAutoMemorySettings();

      setAutoMemoryEnabled(
        settings.auto_memory_enabled
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : (
            "Unable to load automatic "
            + "memory settings."
          )
      );
    } finally {
      setAutoMemoryLoading(false);
    }
  }


  useEffect(() => {
    void loadMemories();
    void loadAutoMemorySettings();
  }, []);


  const filteredMemories =
    useMemo(() => {
      const query =
        searchQuery
          .trim()
          .toLowerCase();

      return memories.filter(
        (memory) => {
          const matchesSearch =
            !query
            || memory.content
              .toLowerCase()
              .includes(query);

          const matchesType =
            typeFilter === "all"
            || memory.memory_type
              === typeFilter;

          const matchesStatus =
            statusFilter === "all"
            || (
              statusFilter === "active"
              && memory.is_active
            )
            || (
              statusFilter === "inactive"
              && !memory.is_active
            );

          return (
            matchesSearch
            && matchesType
            && matchesStatus
          );
        }
      );
    }, [
      memories,
      searchQuery,
      typeFilter,
      statusFilter,
    ]);


  const activeCount =
    memories.filter(
      (memory) =>
        memory.is_active
    ).length;


  const inactiveCount =
    memories.length
    - activeCount;


  function clearMessages() {
    setError("");
    setSuccessMessage("");
  }


  async function handleAutoMemoryToggle() {
    if (
      autoMemoryLoading
      || autoMemorySaving
    ) {
      return;
    }

    clearMessages();

    const nextValue =
      !autoMemoryEnabled;

    setAutoMemorySaving(true);

    try {
      const updated =
        await updateAutoMemorySettings({
          auto_memory_enabled:
            nextValue,
        });

      setAutoMemoryEnabled(
        updated.auto_memory_enabled
      );

      setSuccessMessage(
        updated.auto_memory_enabled
          ? (
            "Automatic memory enabled. "
            + "ORVYN can now safely remember "
            + "useful long-term information "
            + "from normal conversations."
          )
          : (
            "Automatic memory disabled. "
            + "Existing memories were not deleted."
          )
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : (
            "Unable to update automatic "
            + "memory settings."
          )
      );
    } finally {
      setAutoMemorySaving(false);
    }
  }


  function handleTypeFilterChange(
    event:
      ChangeEvent<HTMLSelectElement>
  ) {
    const value =
      event.target.value;

    if (value === "all") {
      setTypeFilter("all");
      return;
    }

    if (isMemoryType(value)) {
      setTypeFilter(value);
    }
  }


  function handleStatusFilterChange(
    event:
      ChangeEvent<HTMLSelectElement>
  ) {
    const value =
      event.target.value;

    if (
      value === "all"
      || value === "active"
      || value === "inactive"
    ) {
      setStatusFilter(value);
    }
  }


  function handleNewTypeChange(
    event:
      ChangeEvent<HTMLSelectElement>
  ) {
    const value =
      event.target.value;

    if (isMemoryType(value)) {
      setNewType(value);
    }
  }


  function handleEditTypeChange(
    event:
      ChangeEvent<HTMLSelectElement>
  ) {
    const value =
      event.target.value;

    if (isMemoryType(value)) {
      setEditType(value);
    }
  }


  function openEdit(
    memory: Memory
  ) {
    clearMessages();

    setEditingMemory(
      memory
    );

    setEditContent(
      memory.content
    );

    setEditType(
      memory.memory_type
    );

    setEditImportance(
      memory.importance
    );
  }


  function closeEdit() {
    setEditingMemory(null);
    setEditContent("");
  }


  async function handleEditSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (!editingMemory) {
      return;
    }

    const content =
      editContent.trim();

    if (!content) {
      setError(
        "Memory content cannot be empty."
      );
      return;
    }

    clearMessages();
    setSaving(true);

    try {
      const updated =
        await updateMemory(
          editingMemory.id,
          {
            content,
            memory_type:
              editType,
            importance:
              editImportance,
          }
        );

      setMemories(
        (current) =>
          current.map(
            (memory) =>
              memory.id
                === updated.id
                ? updated
                : memory
          )
      );

      closeEdit();

      setSuccessMessage(
        "Memory updated successfully."
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to update memory."
      );
    } finally {
      setSaving(false);
    }
  }


  async function handleCreate(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const content =
      newContent.trim();

    if (!content) {
      setError(
        "Memory content cannot be empty."
      );
      return;
    }

    clearMessages();
    setSaving(true);

    try {
      const created =
        await createMemory({
          content,
          memory_type:
            newType,
          importance:
            newImportance,
        });

      setMemories(
        (current) => [
          created,
          ...current,
        ]
      );

      setNewContent("");
      setNewType("fact");
      setNewImportance(0.5);
      setNewMemoryOpen(false);

      setSuccessMessage(
        "Memory added successfully."
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create memory."
      );
    } finally {
      setSaving(false);
    }
  }


  async function handleToggle(
    memory: Memory
  ) {
    clearMessages();

    try {
      const updated =
        await updateMemory(
          memory.id,
          {
            is_active:
              !memory.is_active,
          }
        );

      setMemories(
        (current) =>
          current.map(
            (item) =>
              item.id
                === updated.id
                ? updated
                : item
          )
      );

      setSuccessMessage(
        updated.is_active
          ? "Memory enabled."
          : "Memory disabled."
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to change memory status."
      );
    }
  }


  async function handleDelete(
    memory: Memory
  ) {
    const confirmed =
      window.confirm(
        "Delete this memory permanently?\n\n"
        + memory.content
      );

    if (!confirmed) {
      return;
    }

    clearMessages();

    try {
      await deleteMemory(
        memory.id
      );

      setMemories(
        (current) =>
          current.filter(
            (item) =>
              item.id
              !== memory.id
          )
      );

      setSuccessMessage(
        "Memory deleted permanently."
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete memory."
      );
    }
  }


  return (
    <main
      className="
        min-h-screen
        bg-zinc-950
        px-4
        py-8
        text-zinc-100
        sm:px-6
        lg:px-8
      "
    >
      <div
        className="
          mx-auto
          w-full
          max-w-6xl
        "
      >
        <div
          className="
            mb-8
            flex
            flex-col
            gap-5
            md:flex-row
            md:items-end
            md:justify-between
          "
        >
          <div>
            <p
              className="
                mb-2
                text-sm
                font-medium
                uppercase
                tracking-[0.2em]
                text-zinc-500
              "
            >
              ORVYN
            </p>

            <h1
              className="
                text-3xl
                font-semibold
                tracking-tight
                sm:text-4xl
              "
            >
              Long-Term Memory
            </h1>

            <p
              className="
                mt-3
                max-w-2xl
                text-sm
                leading-6
                text-zinc-400
                sm:text-base
              "
            >
              Review and control
              information ORVYN can
              remember across
              conversations.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              clearMessages();
              setNewMemoryOpen(true);
            }}
            className="
              rounded-xl
              bg-white
              px-5
              py-3
              text-sm
              font-semibold
              text-black
              transition
              hover:bg-zinc-200
            "
          >
            + Add Memory
          </button>
        </div>


        <section
          className="
            mb-6
            rounded-2xl
            border
            border-zinc-800
            bg-zinc-900/60
            p-5
            sm:p-6
          "
        >
          <div
            className="
              flex
              flex-col
              gap-5
              md:flex-row
              md:items-center
              md:justify-between
            "
          >
            <div
              className="
                max-w-3xl
              "
            >
              <div
                className="
                  flex
                  flex-wrap
                  items-center
                  gap-3
                "
              >
                <h2
                  className="
                    text-lg
                    font-semibold
                    text-zinc-100
                  "
                >
                  Automatic Memory
                </h2>

                <span
                  className={`
                    rounded-full
                    px-2.5
                    py-1
                    text-xs
                    font-medium
                    ${
                      autoMemoryLoading
                        ? (
                          "bg-zinc-800 "
                          + "text-zinc-400"
                        )
                        : autoMemoryEnabled
                          ? (
                            "bg-emerald-950 "
                            + "text-emerald-300"
                          )
                          : (
                            "bg-zinc-800 "
                            + "text-zinc-400"
                          )
                    }
                  `}
                >
                  {
                    autoMemoryLoading
                      ? "Loading"
                      : autoMemoryEnabled
                        ? "Enabled"
                        : "Disabled"
                  }
                </span>
              </div>

              <p
                className="
                  mt-2
                  text-sm
                  leading-6
                  text-zinc-400
                "
              >
                Allow ORVYN to
                automatically remember
                useful long-term
                information from your
                normal conversations.
              </p>

              <p
                className="
                  mt-2
                  text-xs
                  leading-5
                  text-zinc-500
                "
              >
                Sensitive information
                and temporary details
                are filtered before
                anything is saved.
                Turning this off does
                not delete memories
                you already saved.
              </p>
            </div>

            <div
              className="
                flex
                shrink-0
                items-center
                gap-3
              "
            >
              <span
                className="
                  text-sm
                  font-medium
                  text-zinc-400
                "
              >
                {
                  autoMemorySaving
                    ? "Saving..."
                    : autoMemoryEnabled
                      ? "On"
                      : "Off"
                }
              </span>

              <button
                type="button"
                role="switch"
                aria-checked={
                  autoMemoryEnabled
                }
                aria-label={
                  "Toggle automatic memory"
                }
                disabled={
                  autoMemoryLoading
                  || autoMemorySaving
                }
                onClick={() =>
                  void handleAutoMemoryToggle()
                }
                className={`
                  relative
                  h-8
                  w-14
                  rounded-full
                  border
                  transition
                  duration-200
                  disabled:cursor-not-allowed
                  disabled:opacity-50
                  ${
                    autoMemoryEnabled
                      ? (
                        "border-emerald-700 "
                        + "bg-emerald-600"
                      )
                      : (
                        "border-zinc-700 "
                        + "bg-zinc-800"
                      )
                  }
                `}
              >
                <span
                  className={`
                    absolute
                    top-1
                    h-6
                    w-6
                    rounded-full
                    bg-white
                    shadow
                    transition-transform
                    duration-200
                    ${
                      autoMemoryEnabled
                        ? (
                          "translate-x-6"
                        )
                        : (
                          "translate-x-1"
                        )
                    }
                  `}
                />
              </button>
            </div>
          </div>
        </section>


        <section
          className="
            mb-6
            grid
            grid-cols-1
            gap-3
            sm:grid-cols-3
          "
        >
          <div
            className="
              rounded-2xl
              border
              border-zinc-800
              bg-zinc-900/60
              p-5
            "
          >
            <p
              className="
                text-sm
                text-zinc-500
              "
            >
              Total Memories
            </p>

            <p
              className="
                mt-2
                text-3xl
                font-semibold
              "
            >
              {memories.length}
            </p>
          </div>

          <div
            className="
              rounded-2xl
              border
              border-zinc-800
              bg-zinc-900/60
              p-5
            "
          >
            <p
              className="
                text-sm
                text-zinc-500
              "
            >
              Active
            </p>

            <p
              className="
                mt-2
                text-3xl
                font-semibold
              "
            >
              {activeCount}
            </p>
          </div>

          <div
            className="
              rounded-2xl
              border
              border-zinc-800
              bg-zinc-900/60
              p-5
            "
          >
            <p
              className="
                text-sm
                text-zinc-500
              "
            >
              Disabled
            </p>

            <p
              className="
                mt-2
                text-3xl
                font-semibold
              "
            >
              {inactiveCount}
            </p>
          </div>
        </section>


        <section
          className="
            mb-6
            rounded-2xl
            border
            border-zinc-800
            bg-zinc-900/40
            p-4
          "
        >
          <div
            className="
              grid
              gap-3
              lg:grid-cols-[1fr_180px_180px]
            "
          >
            <input
              type="search"
              value={
                searchQuery
              }
              onChange={(event) =>
                setSearchQuery(
                  event.target.value
                )
              }
              placeholder="Search memories..."
              className="
                w-full
                rounded-xl
                border
                border-zinc-800
                bg-zinc-950
                px-4
                py-3
                text-sm
                outline-none
                transition
                placeholder:text-zinc-600
                focus:border-zinc-600
              "
            />

            <select
              value={
                typeFilter
              }
              onChange={
                handleTypeFilterChange
              }
              className="
                rounded-xl
                border
                border-zinc-800
                bg-zinc-950
                px-4
                py-3
                text-sm
                outline-none
              "
            >
              <option value="all">
                All Types
              </option>

              {MEMORY_TYPES.map(
                (type) => (
                  <option
                    key={type}
                    value={type}
                  >
                    {
                      formatMemoryType(
                        type
                      )
                    }
                  </option>
                )
              )}
            </select>

            <select
              value={
                statusFilter
              }
              onChange={
                handleStatusFilterChange
              }
              className="
                rounded-xl
                border
                border-zinc-800
                bg-zinc-950
                px-4
                py-3
                text-sm
                outline-none
              "
            >
              <option value="all">
                All Status
              </option>

              <option value="active">
                Active
              </option>

              <option value="inactive">
                Disabled
              </option>
            </select>
          </div>
        </section>


        {error && (
          <div
            className="
              mb-5
              rounded-xl
              border
              border-red-900/60
              bg-red-950/40
              px-4
              py-3
              text-sm
              text-red-300
            "
          >
            {error}
          </div>
        )}


        {successMessage && (
          <div
            className="
              mb-5
              rounded-xl
              border
              border-emerald-900/60
              bg-emerald-950/30
              px-4
              py-3
              text-sm
              text-emerald-300
            "
          >
            {successMessage}
          </div>
        )}


        {loading ? (
          <div
            className="
              rounded-2xl
              border
              border-zinc-800
              bg-zinc-900/40
              p-10
              text-center
              text-zinc-500
            "
          >
            Loading memories...
          </div>
        ) : filteredMemories.length
          === 0 ? (
          <div
            className="
              rounded-2xl
              border
              border-dashed
              border-zinc-800
              p-12
              text-center
            "
          >
            <h2
              className="
                text-lg
                font-medium
              "
            >
              No memories found
            </h2>

            <p
              className="
                mt-2
                text-sm
                text-zinc-500
              "
            >
              ORVYN will show
              your saved memories
              here.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredMemories.map(
              (memory) => (
                <article
                  key={
                    memory.id
                  }
                  className={`
                    rounded-2xl
                    border
                    p-5
                    transition
                    ${
                      memory.is_active
                        ? (
                          "border-zinc-800 "
                          + "bg-zinc-900/50"
                        )
                        : (
                          "border-zinc-900 "
                          + "bg-zinc-950 "
                          + "opacity-60"
                        )
                    }
                  `}
                >
                  <div
                    className="
                      flex
                      flex-col
                      gap-4
                      lg:flex-row
                      lg:items-start
                      lg:justify-between
                    "
                  >
                    <div
                      className="
                        min-w-0
                        flex-1
                      "
                    >
                      <div
                        className="
                          mb-3
                          flex
                          flex-wrap
                          items-center
                          gap-2
                        "
                      >
                        <span
                          className="
                            rounded-full
                            border
                            border-zinc-700
                            bg-zinc-950
                            px-3
                            py-1
                            text-xs
                            font-medium
                            text-zinc-300
                          "
                        >
                          {
                            formatMemoryType(
                              memory.memory_type
                            )
                          }
                        </span>

                        <span
                          className={`
                            rounded-full
                            px-3
                            py-1
                            text-xs
                            ${
                              memory.is_active
                                ? (
                                  "bg-emerald-950 "
                                  + "text-emerald-300"
                                )
                                : (
                                  "bg-zinc-800 "
                                  + "text-zinc-400"
                                )
                            }
                          `}
                        >
                          {
                            memory.is_active
                              ? "Active"
                              : "Disabled"
                          }
                        </span>

                        <span
                          className="
                            text-xs
                            text-zinc-600
                          "
                        >
                          Importance{" "}
                          {
                            Math.round(
                              memory.importance
                              * 100
                            )
                          }
                          %
                        </span>
                      </div>

                      <p
                        className="
                          whitespace-pre-wrap
                          break-words
                          text-sm
                          leading-6
                          text-zinc-200
                          sm:text-base
                        "
                      >
                        {memory.content}
                      </p>

                      <p
                        className="
                          mt-4
                          text-xs
                          text-zinc-600
                        "
                      >
                        Updated{" "}
                        {
                          formatDate(
                            memory.updated_at
                          )
                        }
                      </p>
                    </div>

                    <div
                      className="
                        flex
                        flex-wrap
                        gap-2
                      "
                    >
                      <button
                        type="button"
                        onClick={() =>
                          openEdit(memory)
                        }
                        className="
                          rounded-lg
                          border
                          border-zinc-700
                          px-3
                          py-2
                          text-xs
                          font-medium
                          transition
                          hover:bg-zinc-800
                        "
                      >
                        Edit
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          void handleToggle(
                            memory
                          )
                        }
                        className="
                          rounded-lg
                          border
                          border-zinc-700
                          px-3
                          py-2
                          text-xs
                          font-medium
                          transition
                          hover:bg-zinc-800
                        "
                      >
                        {
                          memory.is_active
                            ? "Disable"
                            : "Enable"
                        }
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          void handleDelete(
                            memory
                          )
                        }
                        className="
                          rounded-lg
                          border
                          border-red-900/60
                          px-3
                          py-2
                          text-xs
                          font-medium
                          text-red-300
                          transition
                          hover:bg-red-950/40
                        "
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </article>
              )
            )}
          </div>
        )}
      </div>


      {newMemoryOpen && (
        <div
          className="
            fixed
            inset-0
            z-50
            flex
            items-center
            justify-center
            bg-black/70
            p-4
          "
        >
          <form
            onSubmit={
              handleCreate
            }
            className="
              w-full
              max-w-xl
              rounded-2xl
              border
              border-zinc-800
              bg-zinc-950
              p-6
              shadow-2xl
            "
          >
            <div
              className="
                mb-6
                flex
                items-start
                justify-between
                gap-4
              "
            >
              <div>
                <h2
                  className="
                    text-xl
                    font-semibold
                  "
                >
                  Add Memory
                </h2>

                <p
                  className="
                    mt-1
                    text-sm
                    text-zinc-500
                  "
                >
                  Save information
                  ORVYN can use in
                  future conversations.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setNewMemoryOpen(
                    false
                  )
                }
                className="
                  text-xl
                  text-zinc-500
                  hover:text-white
                "
              >
                ×
              </button>
            </div>

            <textarea
              value={
                newContent
              }
              onChange={(event) =>
                setNewContent(
                  event.target.value
                )
              }
              rows={5}
              maxLength={5000}
              placeholder="What should ORVYN remember?"
              className="
                w-full
                resize-none
                rounded-xl
                border
                border-zinc-800
                bg-zinc-900
                p-4
                text-sm
                outline-none
                placeholder:text-zinc-600
                focus:border-zinc-600
              "
            />

            <div
              className="
                mt-4
                grid
                gap-4
                sm:grid-cols-2
              "
            >
              <label
                className="
                  text-sm
                  text-zinc-400
                "
              >
                Type

                <select
                  value={
                    newType
                  }
                  onChange={
                    handleNewTypeChange
                  }
                  className="
                    mt-2
                    w-full
                    rounded-xl
                    border
                    border-zinc-800
                    bg-zinc-900
                    px-3
                    py-3
                    text-zinc-100
                  "
                >
                  {MEMORY_TYPES.map(
                    (type) => (
                      <option
                        key={type}
                        value={type}
                      >
                        {
                          formatMemoryType(
                            type
                          )
                        }
                      </option>
                    )
                  )}
                </select>
              </label>

              <label
                className="
                  text-sm
                  text-zinc-400
                "
              >
                Importance:{" "}
                {
                  Math.round(
                    newImportance
                    * 100
                  )
                }
                %

                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={
                    newImportance
                  }
                  onChange={(event) =>
                    setNewImportance(
                      Number(
                        event
                          .target
                          .value
                      )
                    )
                  }
                  className="
                    mt-4
                    w-full
                  "
                />
              </label>
            </div>

            <div
              className="
                mt-6
                flex
                justify-end
                gap-3
              "
            >
              <button
                type="button"
                disabled={saving}
                onClick={() =>
                  setNewMemoryOpen(
                    false
                  )
                }
                className="
                  rounded-xl
                  border
                  border-zinc-800
                  px-4
                  py-2.5
                  text-sm
                  hover:bg-zinc-900
                "
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={
                  saving
                  || !newContent.trim()
                }
                className="
                  rounded-xl
                  bg-white
                  px-5
                  py-2.5
                  text-sm
                  font-semibold
                  text-black
                  disabled:cursor-not-allowed
                  disabled:opacity-50
                "
              >
                {
                  saving
                    ? "Saving..."
                    : "Save Memory"
                }
              </button>
            </div>
          </form>
        </div>
      )}


      {editingMemory && (
        <div
          className="
            fixed
            inset-0
            z-50
            flex
            items-center
            justify-center
            bg-black/70
            p-4
          "
        >
          <form
            onSubmit={
              handleEditSubmit
            }
            className="
              w-full
              max-w-xl
              rounded-2xl
              border
              border-zinc-800
              bg-zinc-950
              p-6
              shadow-2xl
            "
          >
            <div
              className="
                mb-6
                flex
                justify-between
                gap-4
              "
            >
              <div>
                <h2
                  className="
                    text-xl
                    font-semibold
                  "
                >
                  Edit Memory
                </h2>

                <p
                  className="
                    mt-1
                    text-sm
                    text-zinc-500
                  "
                >
                  Updating content
                  regenerates its
                  semantic embedding.
                </p>
              </div>

              <button
                type="button"
                onClick={
                  closeEdit
                }
                className="
                  text-xl
                  text-zinc-500
                  hover:text-white
                "
              >
                ×
              </button>
            </div>

            <textarea
              value={
                editContent
              }
              onChange={(event) =>
                setEditContent(
                  event.target.value
                )
              }
              rows={5}
              maxLength={5000}
              className="
                w-full
                resize-none
                rounded-xl
                border
                border-zinc-800
                bg-zinc-900
                p-4
                text-sm
                outline-none
                focus:border-zinc-600
              "
            />

            <div
              className="
                mt-4
                grid
                gap-4
                sm:grid-cols-2
              "
            >
              <label
                className="
                  text-sm
                  text-zinc-400
                "
              >
                Type

                <select
                  value={
                    editType
                  }
                  onChange={
                    handleEditTypeChange
                  }
                  className="
                    mt-2
                    w-full
                    rounded-xl
                    border
                    border-zinc-800
                    bg-zinc-900
                    px-3
                    py-3
                    text-zinc-100
                  "
                >
                  {MEMORY_TYPES.map(
                    (type) => (
                      <option
                        key={type}
                        value={type}
                      >
                        {
                          formatMemoryType(
                            type
                          )
                        }
                      </option>
                    )
                  )}
                </select>
              </label>

              <label
                className="
                  text-sm
                  text-zinc-400
                "
              >
                Importance:{" "}
                {
                  Math.round(
                    editImportance
                    * 100
                  )
                }
                %

                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={
                    editImportance
                  }
                  onChange={(event) =>
                    setEditImportance(
                      Number(
                        event
                          .target
                          .value
                      )
                    )
                  }
                  className="
                    mt-4
                    w-full
                  "
                />
              </label>
            </div>

            <div
              className="
                mt-6
                flex
                justify-end
                gap-3
              "
            >
              <button
                type="button"
                disabled={saving}
                onClick={
                  closeEdit
                }
                className="
                  rounded-xl
                  border
                  border-zinc-800
                  px-4
                  py-2.5
                  text-sm
                  hover:bg-zinc-900
                "
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={
                  saving
                  || !editContent.trim()
                }
                className="
                  rounded-xl
                  bg-white
                  px-5
                  py-2.5
                  text-sm
                  font-semibold
                  text-black
                  disabled:cursor-not-allowed
                  disabled:opacity-50
                "
              >
                {
                  saving
                    ? "Saving..."
                    : "Save Changes"
                }
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}