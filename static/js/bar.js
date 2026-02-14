(function () {
  const MODAL_TRANSITION_DURATION = 200;
  let activeFilter = "all";
  let subcategoryMap = {};
  let subcategoryLookup = {};

  function getElement(id) {
    return document.getElementById(id);
  }

  function isModalOpen(modal) {
    return modal && !modal.classList.contains("hidden");
  }

  function openAddModal() {
    const modal = getElement("add-modal");
    const box = modal?.querySelector(".modal-box");
    if (!modal || !box) {
      return;
    }

    modal.classList.add("flex");
    modal.classList.remove("hidden");
    requestAnimationFrame(() => {
      box.classList.remove("opacity-0", "scale-95");
      box.classList.add("opacity-100", "scale-100");
    });

    window.setTimeout(() => {
      getElement("name-input")?.focus();
    }, 10);
  }

  function openFilterModal() {
    const modal = getElement("filter-modal");
    const box = modal?.querySelector(".modal-box");
    if (!modal || !box) {
      return;
    }

    modal.classList.add("flex");
    modal.classList.remove("hidden");
    void box.offsetWidth; // force reflow
    box.classList.remove("opacity-0", "translate-y-[-0.5rem]");
    box.classList.add("opacity-100", "translate-y-0");

    window.setTimeout(() => {
      getElement("filter-all")?.focus();
    }, 10);
  }

  function closeAddModal() {
    const modal = getElement("add-modal");
    const box = modal?.querySelector(".modal-box");
    if (!modal || !box) {
      return;
    }

    box.classList.remove("opacity-100", "scale-100");
    box.classList.add("opacity-0", "scale-95");

    window.setTimeout(() => {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    }, MODAL_TRANSITION_DURATION);
  }

  function closeFilterModal() {
    const modal = getElement("filter-modal");
    const box = modal?.querySelector(".modal-box");
    if (!modal || !box) {
      return;
    }

    box.classList.remove("opacity-100", "scale-100");
    box.classList.add("opacity-0", "scale-95");

    window.setTimeout(() => {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    }, MODAL_TRANSITION_DURATION);
  }

  function openNewIngredientModal() {
    const modal = getElement("new-ingredient-modal");
    const box = modal?.querySelector(".modal-box");
    if (!modal || !box) {
      return;
    }

    const currentName = getElement("name-input")?.value.trim() ?? "";
    const newNameInput = getElement("new-ingredient-name");
    if (newNameInput) {
      newNameInput.value = currentName;
    }

    const newCategoryInput = getElement("new-ingredient-category");
    const existingCategory = getElement("category")?.value || "";
    if (newCategoryInput) {
      if (existingCategory) {
        newCategoryInput.value = existingCategory;
      }
      updateSubcategoryOptionsFor(newCategoryInput.value);
    } else {
      updateSubcategoryOptionsFor("");
    }
    const newSubcategoryInput = getElement("new-ingredient-subcategory");
    if (newSubcategoryInput && !newCategoryInput?.value) {
      newSubcategoryInput.value = "";
    }
    toggleNewIngredientButton(false);

    modal.classList.add("flex");
    modal.classList.remove("hidden");
    requestAnimationFrame(() => {
      box.classList.remove("opacity-0", "scale-95");
      box.classList.add("opacity-100", "scale-100");
    });

    window.setTimeout(() => {
      newNameInput?.focus();
    }, 10);
  }

  function closeNewIngredientModal() {
    const modal = getElement("new-ingredient-modal");
    const box = modal?.querySelector(".modal-box");
    if (!modal || !box) {
      return;
    }

    box.classList.remove("opacity-100", "scale-100");
    box.classList.add("opacity-0", "scale-95");

    window.setTimeout(() => {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
      const form = getElement("new-ingredient-form");
      form?.reset();
      const nameInput = getElement("name-input");
      if (nameInput) {
        filterDropdown();
      }
      const wrapper = getElement("new-subcategory-wrapper");
      if (wrapper) {
        wrapper.classList.add("hidden");
      }
      const subSelect = getElement("new-ingredient-subcategory");
      if (subSelect) {
        subSelect.innerHTML = "";
        subSelect.add(new Option("Select a subcategory", "", true, true));
        subSelect.value = "";
      }
    }, MODAL_TRANSITION_DURATION);
  }

  async function submitNewIngredient(event) {
    event.preventDefault();

    const nameInput = getElement("new-ingredient-name");
    const categoryInput = getElement("new-ingredient-category");
    const subCategoryInput = getElement("new-ingredient-subcategory");
    const select = getElement("name");

    const name = nameInput?.value.trim() ?? "";
    let category = categoryInput?.value.trim() ?? "";
    let subCategory = subCategoryInput?.value.trim() ?? "";

    if (!name) {
      showToast("Please enter a name for the ingredient.");
      nameInput?.focus();
      return;
    }

    if (!category) {
      showToast("Please provide a category.");
      categoryInput?.focus();
      return;
    }

    const categoryEntry = subcategoryLookup[category.toLowerCase()];
    if (categoryEntry) {
      category = categoryEntry.original;
      if (categoryEntry.subs.length > 0) {
        if (subCategory) {
          const matchedSub = categoryEntry.subs.find(
            (value) => value.toLowerCase() === subCategory.toLowerCase()
          );
          if (!matchedSub) {
            showToast("Please choose a valid subcategory.");
            subCategoryInput?.focus();
            return;
          }
          subCategory = matchedSub;
        }
      } else {
        subCategory = "";
        if (subCategoryInput) {
          subCategoryInput.value = "";
        }
      }
      if (categoryInput) {
        categoryInput.value = category;
      }
    } else {
      // Category should always exist because it's a select; guard just in case.
      if (categoryInput) {
        categoryInput.value = category;
      }
    }

    if (select) {
      const existing = Array.from(select.options).find(
        (option) => option.value.toLowerCase() === name.toLowerCase()
      );
      if (existing) {
        select.value = existing.value;
        const visibleInput = getElement("name-input");
        if (visibleInput) {
          visibleInput.value = existing.value;
        }
        closeNewIngredientModal();
        showToast(`${existing.value} already exists in your master list.`, 2500);
        updateFields();
        return;
      }
    }

    const formData = new FormData();
    formData.append("name", name);
    formData.append("category", category);
    formData.append("sub_category", subCategory);

    try {
      const response = await fetch("/possible-ingredients", {
        method: "POST",
        body: formData,
        redirect: "follow",
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

   if (select) {
      const option = new Option(name, name, true, true);
      select.add(option);
      select.value = name;
    }

    const visibleInput = getElement("name-input");
    if (visibleInput) {
      visibleInput.value = name;
    }

    const categoryHidden = getElement("category");
    if (categoryHidden) {
      categoryHidden.value = category;
    }
    const subCategoryHidden = getElement("sub_category");
    if (subCategoryHidden) {
      subCategoryHidden.value = subCategory;
    }

    ensureCategoryOption(category);
    mergeSubcategory(category, subCategory);
    updateSubcategoryOptionsFor(category);

    closeNewIngredientModal();
    showToast(`${name} added to master ingredients.`, 2500);
    const addForm = document.querySelector("#add-modal form");
    if (addForm) {
      submitWithFields({ preventDefault: () => {}, target: addForm });
    } else {
      updateFields();
      toggleNewIngredientButton(false);
    }
    } catch (error) {
      console.error("Unable to add ingredient:", error);
      showToast("Unable to add ingredient. Please try again.", 3000);
    }
  }

  function handleKeyDown(event) {
    const filterModal = getElement("filter-modal");
    const addModal = getElement("add-modal");
    const newIngredientModal = getElement("new-ingredient-modal");

    if (event.key === "Escape") {
      if (isModalOpen(addModal)) {
        closeAddModal();
      }
      if (isModalOpen(filterModal)) {
        closeFilterModal();
      }
      if (isModalOpen(newIngredientModal)) {
        closeNewIngredientModal();
      }
    }

    if (event.key === "Enter" && isModalOpen(filterModal) && !isModalOpen(newIngredientModal)) {
      event.preventDefault();
      closeFilterModal();
    }
  }

  function handleModalBackdropClick(event) {
    const addModal = getElement("add-modal");
    const filterModal = getElement("filter-modal");
    const newIngredientModal = getElement("new-ingredient-modal");

    if (addModal && !addModal.classList.contains("hidden") && event.target === addModal) {
      closeAddModal();
    }

    if (filterModal && !filterModal.classList.contains("hidden") && event.target === filterModal) {
      closeFilterModal();
    }

    if (newIngredientModal && !newIngredientModal.classList.contains("hidden") && event.target === newIngredientModal) {
      closeNewIngredientModal();
    }
  }

  function getSearchValue() {
    const input = getElement("filter-all");
    return input ? input.value.trim().toLowerCase() : "";
  }

  function getRows() {
    return Array.from(document.querySelectorAll(".bar-row"));
  }

  function highlightFilterButton(filter) {
    const buttons = document.querySelectorAll(".filter-btn");
    buttons.forEach((btn) => {
      if (btn.dataset.filter === filter) {
        btn.classList.add("bg-background-mid", "text-logo");
      } else {
        btn.classList.remove("bg-background-mid", "text-logo");
      }
    });
  }

  function matchesRowFilter(row, filter) {
    const normalizedFilter = filter.toLowerCase();
    if (normalizedFilter === "all") {
      return true;
    }

    const type = row.dataset.type || "";
    const category = (row.dataset.category || "").toLowerCase();
    const subcategory = (row.dataset.subcategory || "").toLowerCase();

    if (normalizedFilter === "spirit") {
      return type === "spirit";
    }
    if (normalizedFilter === "modifier") {
      return type === "modifier";
    }

    return category === normalizedFilter || subcategory === normalizedFilter;
  }

  function toggleNewIngredientButton(shouldShow) {
    const trigger = getElement("new-ingredient-trigger");
    if (!trigger) {
      return;
    }
    trigger.classList.toggle("hidden", !shouldShow);
    trigger.classList.toggle("flex", shouldShow);
  }

  function ensureCategoryOption(category) {
    if (!category) {
      return;
    }
    const select = getElement("new-ingredient-category");
    if (!select) {
      return;
    }
    const exists = Array.from(select.options).some(
      (option) => option.value.toLowerCase() === category.toLowerCase()
    );
    if (!exists) {
      const option = new Option(category, category, false, false);
      select.add(option);
    }
  }

  function mergeSubcategory(category, subcategory) {
    if (!category) {
      return;
    }
    const normalized = category.toLowerCase();
    let entry = subcategoryLookup[normalized];
    if (!entry) {
      const subs = subcategory ? [subcategory] : [];
      subcategoryLookup[normalized] = { original: category, subs };
      subcategoryMap[category] = subs;
      return;
    }

    if (!subcategoryMap[entry.original]) {
      subcategoryMap[entry.original] = entry.subs;
    }

    if (subcategory) {
      const existingSubs = entry.subs.map((value) => value.toLowerCase());
      if (!existingSubs.includes(subcategory.toLowerCase())) {
        entry.subs.push(subcategory);
        subcategoryMap[entry.original] = entry.subs;
      }
    }
    updateSubcategoryOptionsFor(entry.original);
  }

  function updateSubcategoryOptionsFor(category) {
    const wrapper = getElement("new-subcategory-wrapper");
    const select = getElement("new-ingredient-subcategory");
    if (!wrapper || !select) {
      return;
    }

    select.innerHTML = "";
    select.add(new Option("Select a subcategory", ""));
    select.value = "";

    if (!category) {
      wrapper.classList.add("hidden");
      return;
    }

    const entry = subcategoryLookup[category.toLowerCase()];
    const subs = entry ? entry.subs : [];
    if (subs.length === 0) {
      wrapper.classList.add("hidden");
      return;
    }

    subs.forEach((value) => {
      const option = new Option(value, value, false, false);
      select.add(option);
    });
    wrapper.classList.remove("hidden");
  }

  function updateRowVisibility() {
    const searchValue = getSearchValue();
    const rows = getRows();
    let visibleCount = 0;

    rows.forEach((row) => {
      const name = (row.dataset.name || "").toLowerCase();
      const category = (row.dataset.category || "").toLowerCase();
      const subcategory = (row.dataset.subcategory || "").toLowerCase();

      const matchesText =
        !searchValue ||
        [name, category, subcategory].some((value) => value.includes(searchValue));
      const matchesFilter = matchesRowFilter(row, activeFilter);
      const shouldShow = matchesText && matchesFilter;

      row.style.display = shouldShow ? "" : "none";
      if (shouldShow) {
        visibleCount += 1;
      }
    });

    updateCategorySections();

    const noResults = getElement("bar-no-results");
    if (noResults) {
      noResults.classList.toggle("hidden", visibleCount !== 0);
    }

    toggleNewIngredientButton(Boolean(searchValue) && visibleCount === 0);
  }

  function updateCategorySections() {
    const sections = document.querySelectorAll(".bar-category");
    sections.forEach((section) => {
      const panel = section.querySelector(".bar-category-panel");
      if (!panel) {
        return;
      }
      const rows = Array.from(panel.querySelectorAll(".bar-row"));
      const visibleRows = rows.filter((row) => row.style.display !== "none");
      const countLabel = section.querySelector(".bar-category-count");
      if (countLabel) {
        const count = visibleRows.length;
        countLabel.textContent = `${count} item${count === 1 ? "" : "s"}`;
      }
      section.classList.toggle("hidden", visibleRows.length === 0);
    });
  }

  function clearFilter() {
    const input = getElement("filter-all");
    const clearButton = getElement("clear-filter-btn");
    if (input) {
      input.value = "";
    }
    if (clearButton) {
      clearButton.classList.add("invisible", "opacity-0", "pointer-events-none");
      clearButton.setAttribute("aria-hidden", "true");
    }
    updateRowVisibility();
    toggleNewIngredientButton(false);
  }

  async function submitWithFields(event) {
    event.preventDefault();

    const form = event.target;
    const name = getElement("name")?.value;
    const categoryInput = getElement("category");
    const subCategoryInput = getElement("sub_category");

    if (!categoryInput || !subCategoryInput) {
      return false;
    }

    categoryInput.value = "";
    subCategoryInput.value = "";

    if (!name) {
      window.alert("Please select a valid item.");
      return false;
    }

    try {
      const response = await fetch(`/ingredient-details/${encodeURIComponent(name)}`);
      const data = await response.json();

      if (data.error) {
        window.alert(data.error);
        return false;
      }

      if (data.category) {
        categoryInput.value = data.category;
      }
      if (data.sub_category) {
        subCategoryInput.value = data.sub_category;
      }

      toggleNewIngredientButton(false);
      form.submit();
      return true;
    } catch (error) {
      console.error("Error fetching ingredient details:", error);
      window.alert("There was a problem adding the item.");
      return false;
    }
  }

  function filterDropdown() {
    const inputEl = getElement("name-input");
    const select = getElement("name");
    const dropdown = getElement("name-dropdown");

    if (!inputEl || !select || !dropdown) {
      return;
    }

    const input = inputEl.value.trim().toLowerCase();
    dropdown.innerHTML = "";

    if (!input) {
      dropdown.classList.add("hidden");
      select.value = "";
      getElement("category").value = "";
      getElement("sub_category").value = "";
      toggleNewIngredientButton(false);
      return;
    }

    const options = Array.from(select.options).slice(1);
    const filteredOptions = options.filter((option) =>
      option.value.toLowerCase().includes(input)
    );

    if (!filteredOptions.length) {
      dropdown.classList.add("hidden");
      toggleNewIngredientButton(true);
      return;
    }

    dropdown.classList.remove("hidden");
    toggleNewIngredientButton(false);
    filteredOptions.forEach((option) => {
      const item = document.createElement("div");
      item.textContent = option.value;
      item.className = "px-3 py-2 text-text-normal hover:bg-background-mid cursor-pointer transition";
      item.setAttribute("role", "option");
      item.addEventListener("click", () => {
        inputEl.value = option.value;
        select.value = option.value;
        dropdown.classList.add("hidden");
        toggleNewIngredientButton(false);
        updateFields();
      });
      dropdown.appendChild(item);
    });
  }

  function clearIngredientFields() {
    const nameInput = getElement("name-input");
    const select = getElement("name");
    const categoryInput = getElement("category");
    const subCategoryInput = getElement("sub_category");
    const dropdown = getElement("name-dropdown");

    if (nameInput) nameInput.value = "";
    if (select) select.value = "";
    if (categoryInput) categoryInput.value = "";
    if (subCategoryInput) subCategoryInput.value = "";
    dropdown?.classList.add("hidden");
    toggleNewIngredientButton(false);
  }

  function updateFields() {
    const name = getElement("name")?.value;
    const categoryInput = getElement("category");
    const subCategoryInput = getElement("sub_category");

    if (!name || !categoryInput || !subCategoryInput) {
      return;
    }

    categoryInput.value = "";
    subCategoryInput.value = "";

    fetch(`/ingredient-details/${encodeURIComponent(name)}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          window.alert(data.error);
          return;
        }

        if (data.category) {
          categoryInput.value = data.category;
        }

        if (data.sub_category) {
          subCategoryInput.value = data.sub_category;
        }
        toggleNewIngredientButton(false);
      })
      .catch((error) => {
        console.error("Error fetching ingredient details:", error);
      });
  }

  function sortTable(tableId, colIndex, headerDiv) {
    const table = getElement(tableId);
    const tbody = table?.querySelector("tbody");
    if (!table || !tbody) {
      return;
    }

    const rows = Array.from(tbody.querySelectorAll("tr"));
    const current = headerDiv.getAttribute("data-sort") || "none";
    const newDirection = current === "asc" ? "desc" : "asc";

    const headers = headerDiv.parentElement.querySelectorAll("div[data-col]");
    headers.forEach((h) => h.removeAttribute("data-sort"));
    headerDiv.setAttribute("data-sort", newDirection);

    rows.sort((a, b) => {
      const cellA = a.children[colIndex].textContent.trim().toLowerCase();
      const cellB = b.children[colIndex].textContent.trim().toLowerCase();
      return newDirection === "asc"
        ? cellA.localeCompare(cellB)
        : cellB.localeCompare(cellA);
    });

    rows.forEach((row) => tbody.appendChild(row));
  }

  function filterTable(filter) {
    const normalized = filter.toLowerCase();
    if (activeFilter === normalized) {
      activeFilter = "all";
    } else {
      activeFilter = normalized;
    }
    highlightFilterButton(activeFilter);
    updateRowVisibility();
  }

  function filterAllTables() {
    const clearButton = getElement("clear-filter-btn");
    const searchValue = getSearchValue();
    if (clearButton) {
      clearButton.classList.toggle("invisible", !searchValue);
      clearButton.classList.toggle("opacity-0", !searchValue);
      clearButton.classList.toggle("pointer-events-none", !searchValue);
      clearButton.setAttribute("aria-hidden", String(!searchValue));
    }
    updateRowVisibility();
  }

  function initDeleteModal() {
    const deleteModal = getElement("delete-modal");
    const confirmButton = getElement("confirm-delete");
    const cancelButton = getElement("cancel-delete");
    const message = getElement("delete-modal-message");
    if (!deleteModal || !confirmButton || !cancelButton || !message) {
      return;
    }

    let itemToDelete = null;
    const deleteButtons = document.querySelectorAll(".delete-item");
    deleteButtons.forEach((button) => {
      button.addEventListener("click", () => {
        itemToDelete = button.getAttribute("data-name");
        message.textContent = `Are you sure you want to delete ${itemToDelete} from your bar?`;
        deleteModal.classList.remove("hidden");
      });
    });

    confirmButton.addEventListener("click", () => {
      if (!itemToDelete) {
        return;
      }
      fetch(`/bar/delete_bar_item/${itemToDelete}`, {
        method: "DELETE",
      })
        .then((response) => response.json())
        .then(() => {
          deleteModal.classList.add("hidden");
          window.location.reload();
        })
        .catch((error) => {
          console.error("Error deleting item:", error);
          window.alert("Error deleting item.");
          deleteModal.classList.add("hidden");
        });
    });

    cancelButton.addEventListener("click", () => {
      deleteModal.classList.add("hidden");
      itemToDelete = null;
    });
  }

  function initFilterButtons() {
    document.querySelectorAll(".filter-btn").forEach((button) => {
      button.addEventListener("click", () => {
        filterTable(button.dataset.filter);
      });
    });
  }

  function initTopFiltersToggle() {
    const toggle = getElement("bar-filters-toggle");
    const panel = getElement("bar-filters-panel");
    const plusIcon = getElement("bar-filters-plus");
    const minusIcon = getElement("bar-filters-minus");
    if (!toggle || !panel || !plusIcon || !minusIcon) {
      return;
    }

    const setState = (expanded) => {
      panel.classList.toggle("hidden", !expanded);
      plusIcon.classList.toggle("hidden", expanded);
      minusIcon.classList.toggle("hidden", !expanded);
      toggle.setAttribute("aria-expanded", String(expanded));
    };

    setState(false);

    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") !== "true";
      setState(expanded);
    });
  }

  function initAccordion() {
    document.querySelectorAll(".bar-category-toggle").forEach((button) => {
      button.addEventListener("click", () => {
        const targetId = button.dataset.target;
        const panel = targetId ? document.getElementById(targetId) : null;
        if (!panel) {
          return;
        }
        const expanded = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!expanded));
        panel.classList.toggle("hidden", expanded);
        const chevron = button.querySelector("[data-chevron]");
        if (chevron) {
          chevron.style.transform = expanded ? "" : "rotate(180deg)";
        }
      });
      const targetId = button.dataset.target;
      const panel = targetId ? document.getElementById(targetId) : null;
      if (panel) {
        button.setAttribute("aria-expanded", "false");
        panel.classList.add("hidden");
        const chevron = button.querySelector("[data-chevron]");
        if (chevron) {
          chevron.style.transform = "";
        }
      }
    });
  }

  function handleDropdownDismiss(event) {
    const dropdown = getElement("name-dropdown");
    const input = getElement("name-input");
    if (!dropdown || !input) {
      return;
    }

    if (!input.contains(event.target) && !dropdown.contains(event.target)) {
      dropdown.classList.add("hidden");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("click", handleModalBackdropClick);
    document.addEventListener("click", handleDropdownDismiss);

    const newIngredientModal = getElement("new-ingredient-modal");
    if (newIngredientModal) {
      try {
        const parsed = JSON.parse(newIngredientModal.dataset.subcategories || "{}");
        subcategoryMap = {};
        subcategoryLookup = {};
        Object.keys(parsed || {}).forEach((key) => {
          const uniqueSubs = Array.from(
            new Set((parsed[key] || []).map((value) => (value || "").trim()))
          ).filter(Boolean);
          subcategoryMap[key] = uniqueSubs;
          subcategoryLookup[key.toLowerCase()] = { original: key, subs: uniqueSubs };
        });
      } catch (error) {
        console.error("Unable to parse subcategory dataset:", error);
      }
    }

    const newIngredientCategoryInput = getElement("new-ingredient-category");
    if (newIngredientCategoryInput) {
      newIngredientCategoryInput.addEventListener("input", () => {
        updateSubcategoryOptionsFor(newIngredientCategoryInput.value);
        const subInput = getElement("new-ingredient-subcategory");
        if (subInput) {
          const options = Array.from(subInput.options)
            .map((opt) => opt.value.toLowerCase())
            .filter(Boolean);
          if (subInput.value && !options.includes(subInput.value.toLowerCase())) {
            subInput.value = "";
          }
        }
      });
      updateSubcategoryOptionsFor(newIngredientCategoryInput.value);
    }

    const newIngredientForm = getElement("new-ingredient-form");
    if (newIngredientForm) {
      newIngredientForm.addEventListener("submit", submitNewIngredient);
    }

    highlightFilterButton(activeFilter);
    initDeleteModal();
    initFilterButtons();
    initTopFiltersToggle();
    initAccordion();
    filterAllTables();
  });

  window.openAddModal = openAddModal;
  window.openFilterModal = openFilterModal;
  window.closeAddModal = closeAddModal;
  window.closeFilterModal = closeFilterModal;
  window.openNewIngredientModal = openNewIngredientModal;
  window.closeNewIngredientModal = closeNewIngredientModal;
  window.clearFilter = clearFilter;
  window.submitWithFields = submitWithFields;
  window.filterDropdown = filterDropdown;
  window.clearIngredientFields = clearIngredientFields;
  window.updateFields = updateFields;
  window.sortTable = sortTable;
  window.filterTable = filterTable;
  window.filterAllTables = filterAllTables;
})();
