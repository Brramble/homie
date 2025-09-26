// Theme toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('theme-toggle');
    const userMenuButton = document.getElementById('user-menu-button');
    const userMenu = document.getElementById('user-menu');
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');

    // Theme is already applied in the head script, so no need to reapply here
    // Just ensure the toggle button shows the correct state
    const isDark = document.documentElement.classList.contains('dark');
    
    // Theme toggle
    if (themeToggle) {
        // Set initial state of toggle based on current theme
        const updateToggleState = () => {
            const isDark = document.documentElement.classList.contains('dark');
            themeToggle.setAttribute('aria-checked', isDark ? 'true' : 'false');
        };
        
        // Set initial state
        updateToggleState();
        
        themeToggle.addEventListener('click', function() {
            const currentlyDark = document.documentElement.classList.contains('dark');
            
            if (currentlyDark) {
                document.documentElement.classList.remove('dark');
                localStorage.setItem('theme', 'light');
            } else {
                document.documentElement.classList.add('dark');
                localStorage.setItem('theme', 'dark');
            }
            
            // Update toggle state
            updateToggleState();
        });
    }

    // User menu toggle
    if (userMenuButton && userMenu) {
        userMenuButton.addEventListener('click', function(e) {
            e.stopPropagation();
            userMenu.classList.toggle('hidden');
        });

        // Close user menu when clicking outside
        document.addEventListener('click', function() {
            userMenu.classList.add('hidden');
        });
    }

    // Mobile menu toggle
    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', function() {
            mobileMenu.classList.toggle('hidden');
        });
    }

    // Auto-hide flash messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(100%)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Utility functions
function confirmAction(message) {
    return confirm(message);
}

function toggleComplete(itemId, type, element) {
    fetch(`/toggle_${type}/${itemId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // For shopping list, handle DOM updates without page reload
            if (type === 'shopping') {
                updateShoppingItemDOM(itemId, data.item, element);
            } else if (type === 'chore') {
                updateChoreItemDOM(itemId, data.chore, element);
            } else {
                // For other types, still reload for now
                location.reload();
            }
        } else {
            alert('Error updating item');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error updating item');
    });
}

function updateShoppingItemDOM(itemId, itemData, element) {
    const itemRow = element.closest('.item-row');
    const currentList = itemRow.closest('.bg-white');
    
    if (itemData.completed) {
        // Item was marked as completed - move to completed section
        moveItemToCompletedSection(itemId, itemData, itemRow);
    } else {
        // Item was unchecked - move back to active list
        moveItemToActiveList(itemId, itemData, itemRow);
    }
    
    // Update counters
    updateItemCounters();
}

function moveItemToCompletedSection(itemId, itemData, itemRow) {
    // Remove from current list
    itemRow.remove();
    
    // Get or create completed section
    let completedSection = document.getElementById('completed-section');
    if (!completedSection) {
        // Create completed section if it doesn't exist
        const mainList = document.querySelector('.max-w-4xl');
        const completedHTML = `
            <div class="bg-white dark:bg-gray-800 shadow rounded-lg mt-8">
                <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                    <button onclick="document.getElementById('completed-section').classList.toggle('hidden')"
                            class="flex items-center justify-between w-full text-left">
                        <h3 class="text-lg font-medium text-gray-900 dark:text-white">
                            Recently Completed Items
                        </h3>
                        <div class="flex items-center space-x-2">
                            <span class="text-sm text-gray-500 dark:text-gray-400 completed-count">1 completed</span>
                            <i class="fas fa-chevron-down text-gray-400"></i>
                        </div>
                    </button>
                </div>
                <div id="completed-section" class="divide-y divide-gray-200 dark:divide-gray-700">
                </div>
            </div>
        `;
        mainList.insertAdjacentHTML('beforeend', completedHTML);
        completedSection = document.getElementById('completed-section');
    }
    
    // Create completed item HTML
    const completedItemHTML = `
        <div class="item-row p-6 bg-gray-50 dark:bg-gray-700">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-4">
                    <button onclick="toggleComplete(${itemId}, 'shopping', this)"
                            class="flex-shrink-0 h-5 w-5 rounded bg-green-500 border-green-500 flex items-center justify-center hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 transition-colors cursor-pointer">
                        <i class="fas fa-check text-white text-xs"></i>
                    </button>
                    <div>
                        <h4 class="text-lg font-medium line-through text-gray-500 dark:text-gray-400">
                            ${itemData.item_name}
                        </h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400">
                            Completed by ${itemData.completed_by_username} on ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                        </p>
                    </div>
                </div>
                <div class="relative action-dropdown">
                    <button onclick="toggleActionMenu('completed-shopping-menu-${itemId}')"
                            class="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 focus:outline-none rounded-full hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <div id="completed-shopping-menu-${itemId}" class="action-menu hidden absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-20 border border-gray-200 dark:border-gray-600">
                        <button onclick="toggleComplete(${itemId}, 'shopping', this)"
                                class="block w-full text-left px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-t-md transition-colors">
                            <i class="fas fa-undo mr-2"></i>Move back to list
                        </button>
                        <button onclick="deleteItem(${itemId}, 'shopping', this)"
                                class="block w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-b-md transition-colors border-t border-gray-200 dark:border-gray-600">
                            <i class="fas fa-trash mr-2"></i>Delete
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    completedSection.insertAdjacentHTML('beforeend', completedItemHTML);
}

function moveItemToActiveList(itemId, itemData, itemRow) {
    // Remove from completed section
    itemRow.remove();
    
    // Find the active items container
    const activeItemsContainer = document.querySelector('.bg-white.dark\\:bg-gray-800 .divide-y');
    
    // Check if there's an empty state message to remove
    const emptyState = activeItemsContainer.querySelector('.p-12.text-center');
    if (emptyState) {
        emptyState.remove();
    }
    
    // Create active item HTML
    const activeItemHTML = `
        <div class="item-row p-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-4">
                    <button onclick="toggleComplete(${itemId}, 'shopping', this)"
                            class="flex-shrink-0 h-5 w-5 rounded border-2 border-gray-300 dark:border-gray-600 hover:border-green-500 focus:outline-none focus:ring-2 focus:ring-green-500 transition-colors cursor-pointer">
                    </button>
                    <div>
                        <h4 class="text-lg font-medium text-gray-900 dark:text-white">
                            ${itemData.item_name}
                        </h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400">
                            Added by ${itemData.added_by_username} on ${new Date(itemData.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                        </p>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <div class="relative action-dropdown">
                        <button onclick="toggleActionMenu('shopping-menu-${itemId}')"
                                class="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 focus:outline-none rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <div id="shopping-menu-${itemId}" class="action-menu hidden absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-20 border border-gray-200 dark:border-gray-600">
                            <button onclick="toggleComplete(${itemId}, 'shopping', this)"
                                    class="block w-full text-left px-4 py-2 text-sm text-green-600 dark:text-green-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-t-md transition-colors">
                                <i class="fas fa-check mr-2"></i>Mark Done
                            </button>
                            <button onclick="deleteItem(${itemId}, 'shopping', this)"
                                    class="block w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-b-md transition-colors border-t border-gray-200 dark:border-gray-600">
                                <i class="fas fa-trash mr-2"></i>Delete
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    activeItemsContainer.insertAdjacentHTML('beforeend', activeItemHTML);
}

function updateItemCounters() {
    // Update active items counter - only count items in the main active list, not completed section
    const activeItemsList = document.querySelector('.bg-white.dark\\:bg-gray-800 .divide-y');
    const activeItems = activeItemsList ? activeItemsList.querySelectorAll('.item-row') : [];
    const activeCounter = document.querySelector('.shopping-item-counter');
    if (activeCounter) {
        const count = activeItems.length;
        activeCounter.textContent = `${count} item${count !== 1 ? 's' : ''}`;
    }
    
    // Update completed items counter
    const completedItems = document.querySelectorAll('#completed-section .item-row');
    const completedCounter = document.querySelector('.completed-count');
    if (completedCounter) {
        const count = completedItems.length;
        completedCounter.textContent = `${count} completed`;
    }
}

// Chore-specific functions
function updateChoreItemDOM(choreId, choreData, element) {
    const choreRow = element.closest('.item-row');
    const currentList = choreRow.closest('.bg-white');
    
    if (choreData.completed) {
        // Chore was marked as completed - move to completed section
        moveChoreToCompletedSection(choreId, choreData, choreRow);
    } else {
        // Chore was unchecked - move back to active list
        moveChoreToActiveList(choreId, choreData, choreRow);
    }
    
    // Update counters
    updateChoreCounters();
}

function moveChoreToCompletedSection(choreId, choreData, choreRow) {
    // Remove from current list
    choreRow.remove();
    
    // Get or create completed section
    let completedSection = document.getElementById('completed-chores-section');
    if (!completedSection) {
        // Create completed section if it doesn't exist
        const mainList = document.querySelector('.max-w-4xl');
        const completedHTML = `
            <div class="bg-white dark:bg-gray-800 shadow rounded-lg mt-8">
                <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                    <button onclick="document.getElementById('completed-chores-section').classList.toggle('hidden')"
                            class="flex items-center justify-between w-full text-left">
                        <h3 class="text-lg font-medium text-gray-900 dark:text-white">
                            Recently Completed Chores
                        </h3>
                        <div class="flex items-center space-x-2">
                            <span class="text-sm text-gray-500 dark:text-gray-400 completed-chores-count">1 completed</span>
                            <i class="fas fa-chevron-down text-gray-400"></i>
                        </div>
                    </button>
                </div>
                <div id="completed-chores-section" class="divide-y divide-gray-200 dark:divide-gray-700">
                </div>
            </div>
        `;
        mainList.insertAdjacentHTML('beforeend', completedHTML);
        completedSection = document.getElementById('completed-chores-section');
    }
    
    // Create completed chore HTML
    const completedChoreHTML = `
        <div class="item-row p-6 bg-gray-50 dark:bg-gray-700">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-4">
                    <button onclick="toggleComplete(${choreId}, 'chore', this)"
                            class="flex-shrink-0 h-5 w-5 rounded bg-green-500 border-green-500 flex items-center justify-center hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 transition-colors cursor-pointer">
                        <i class="fas fa-check text-white text-xs"></i>
                    </button>
                    <div>
                        <h4 class="text-lg font-medium line-through text-gray-500 dark:text-gray-400">
                            ${choreData.chore_name}
                        </h4>
                        ${choreData.description ? `<p class="text-sm text-gray-400 dark:text-gray-500 line-through">${choreData.description}</p>` : ''}
                        <p class="text-sm text-gray-500 dark:text-gray-400">
                            Completed by ${choreData.completed_by_username ? choreData.completed_by_username.charAt(0).toUpperCase() + choreData.completed_by_username.slice(1) : 'Unknown'} on ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                        </p>
                    </div>
                </div>
                <div class="relative action-dropdown">
                    <button onclick="toggleActionMenu('completed-chore-menu-${choreId}')"
                            class="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 focus:outline-none rounded-full hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <div id="completed-chore-menu-${choreId}" class="action-menu hidden absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-20 border border-gray-200 dark:border-gray-600">
                        <button onclick="toggleComplete(${choreId}, 'chore', this)"
                                class="block w-full text-left px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-t-md transition-colors">
                            <i class="fas fa-undo mr-2"></i>Move back to list
                        </button>
                        <button onclick="deleteItem(${choreId}, 'chore', this)"
                                class="block w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-b-md transition-colors border-t border-gray-200 dark:border-gray-600">
                            <i class="fas fa-trash mr-2"></i>Delete
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    completedSection.insertAdjacentHTML('beforeend', completedChoreHTML);
}

function moveChoreToActiveList(choreId, choreData, choreRow) {
    // Remove from completed section
    choreRow.remove();
    
    // Find the active chores container
    const activeChoresContainer = document.querySelector('.bg-white.dark\\:bg-gray-800 .divide-y');
    
    // Check if there's an empty state message to remove
    const emptyState = activeChoresContainer.querySelector('.p-12.text-center');
    if (emptyState) {
        emptyState.remove();
    }
    
    // Create active chore HTML
    const activeChoreHTML = `
        <div class="item-row p-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-4">
                    <button onclick="toggleComplete(${choreId}, 'chore', this)"
                            class="flex-shrink-0 h-5 w-5 rounded border-2 border-gray-300 dark:border-gray-600 hover:border-green-500 focus:outline-none focus:ring-2 focus:ring-green-500 transition-colors cursor-pointer">
                    </button>
                    <div>
                        <h4 class="text-lg font-medium text-gray-900 dark:text-white">
                            ${choreData.chore_name}
                        </h4>
                        ${choreData.description ? `<p class="text-sm text-gray-600 dark:text-gray-400">${choreData.description}</p>` : ''}
                        <div class="flex flex-wrap gap-4 mt-2">
                            <p class="text-sm text-gray-500 dark:text-gray-400">
                                Added by ${choreData.added_by_username ? choreData.added_by_username.charAt(0).toUpperCase() + choreData.added_by_username.slice(1) : 'Unknown'}
                            </p>
                            ${choreData.assigned_to_username ? `<p class="text-sm text-gray-500 dark:text-gray-400">
                                Assigned to ${choreData.assigned_to_username.charAt(0).toUpperCase() + choreData.assigned_to_username.slice(1)}
                            </p>` : ''}
                        </div>
                    </div>
                </div>
                <div class="relative action-dropdown">
                    <button onclick="toggleActionMenu('chore-menu-${choreId}')"
                            class="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 focus:outline-none rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <div id="chore-menu-${choreId}" class="action-menu hidden absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-20 border border-gray-200 dark:border-gray-600">
                        <button onclick="toggleComplete(${choreId}, 'chore', this)"
                                class="block w-full text-left px-4 py-2 text-sm text-green-600 dark:text-green-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-t-md transition-colors">
                            <i class="fas fa-check mr-2"></i>Mark Done
                        </button>
                        <button onclick="deleteItem(${choreId}, 'chore', this)"
                                class="block w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-b-md transition-colors border-t border-gray-200 dark:border-gray-600">
                            <i class="fas fa-trash mr-2"></i>Delete
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    activeChoresContainer.insertAdjacentHTML('beforeend', activeChoreHTML);
}

function updateChoreCounters() {
    // Update active chores counter - only count items in the main active list, not completed section
    const activeChoresList = document.querySelector('.bg-white.dark\\:bg-gray-800 .divide-y');
    const activeChores = activeChoresList ? activeChoresList.querySelectorAll('.item-row') : [];
    const activeCounter = document.querySelector('.chores-item-counter');
    if (activeCounter) {
        const count = activeChores.length;
        activeCounter.textContent = `${count} chore${count !== 1 ? 's' : ''}`;
    }
    
    // Update completed chores counter
    const completedChores = document.querySelectorAll('#completed-chores-section .item-row');
    const completedCounter = document.querySelector('.completed-chores-count');
    if (completedCounter) {
        const count = completedChores.length;
        completedCounter.textContent = `${count} completed`;
    }
}

function deleteItem(itemId, type, element) {
    if (confirmAction('Are you sure you want to delete this item?')) {
        fetch(`/delete_${type}/${itemId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                element.closest('.item-row').remove();
            } else {
                alert('Error deleting item');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error deleting item');
        });
    }
}

// Mobile-friendly dropdown menu functionality
function toggleActionMenu(menuId) {
    const menu = document.getElementById(menuId);
    const isHidden = menu.classList.contains('hidden');
    
    // Close all other menus first
    document.querySelectorAll('.action-menu').forEach(m => {
        if (m.id !== menuId) {
            m.classList.add('hidden');
        }
    });
    
    // Toggle current menu
    if (isHidden) {
        menu.classList.remove('hidden');
    } else {
        menu.classList.add('hidden');
    }
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(event) {
    if (!event.target.closest('.action-dropdown')) {
        document.querySelectorAll('.action-menu').forEach(menu => {
            menu.classList.add('hidden');
        });
    }
});