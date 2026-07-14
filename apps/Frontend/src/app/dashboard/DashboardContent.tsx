"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Toaster } from "sonner";
import { authService } from "@/services/auth.service";
import type { User } from "@supabase/supabase-js";
import Sidebar from '@/components/dashboard/Sidebar'
import ContentEditor from '@/components/dashboard/ContentEditor'
import AIPanel from '@/components/dashboard/AIPanel'
import DashboardHome from '@/components/dashboard/DashboardHome'
import SearchOverlay from '@/components/dashboard/SearchOverlay'
import DashboardSettings from '@/components/dashboard/DashboardSettings'
import DashboardTrash from '@/components/dashboard/DashboardTrash'
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { v4 as uuidv4 } from 'uuid';

interface DashboardContentProps {
  user: User;
  initialView?: "home" | "page" | "settings" | "trash";
}

export type PageItem = {
  id: string;
  title: string;
  content: string;
  parentId: string | null;
  isOpen?: boolean;
  icon?: string;
}

// ─── Helper: map DB row (snake_case) → PageItem (camelCase) ──────────────────
function dbRowToPageItem(row: any): PageItem {
  return {
    id: row.id,
    title: row.title ?? 'Untitled',
    content: row.content ?? '',
    parentId: row.parent_id ?? null,
    isOpen: row.is_open ?? true,
    icon: row.icon ?? undefined,
  };
}

export default function DashboardContent({ user, initialView = "home" }: DashboardContentProps) {
  const [pages, setPages] = useState<PageItem[]>([]);
  const [activePageId, setActivePageId] = useState<string>('');
  const [activeView, setActiveView] = useState<"home" | "page" | "settings" | "trash">(initialView);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(initialView === "settings");
  const [isLoading, setIsLoading] = useState(true);

  const isMockUser = user.id === "mock-user-id";

  useEffect(() => {
    setIsSettingsOpen(initialView === "settings");
    setActiveView(initialView);
  }, [initialView]);

  useEffect(() => {
    // Prevent body/html scrolling/shifting while in dashboard to avoid layout shifting
    const origBodyStyle = {
      position: document.body.style.position,
      overflow: document.body.style.overflow,
      width: document.body.style.width,
      height: document.body.style.height,
    };
    const origHtmlStyle = {
      position: document.documentElement.style.position,
      overflow: document.documentElement.style.overflow,
      width: document.documentElement.style.width,
      height: document.documentElement.style.height,
    };

    document.body.style.position = "fixed";
    document.body.style.overflow = "hidden";
    document.body.style.width = "100%";
    document.body.style.height = "100%";

    document.documentElement.style.position = "fixed";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.width = "100%";
    document.documentElement.style.height = "100%";

    // Force scroll position to 0,0 to counter any browser-level focus auto-scrolling
    const forceScrollTop = () => {
      window.scrollTo(0, 0);
      document.body.scrollTop = 0;
      document.documentElement.scrollTop = 0;
    };

    window.addEventListener("scroll", forceScrollTop, { passive: true });
    window.addEventListener("resize", forceScrollTop, { passive: true });
    document.addEventListener("focusin", forceScrollTop, { passive: true });

    // Execute immediately
    forceScrollTop();

    return () => {
      document.body.style.position = origBodyStyle.position;
      document.body.style.overflow = origBodyStyle.overflow;
      document.body.style.width = origBodyStyle.width;
      document.body.style.height = origBodyStyle.height;

      document.documentElement.style.position = origHtmlStyle.position;
      document.documentElement.style.overflow = origHtmlStyle.overflow;
      document.documentElement.style.width = origHtmlStyle.width;
      document.documentElement.style.height = origHtmlStyle.height;

      window.removeEventListener("scroll", forceScrollTop);
      window.removeEventListener("resize", forceScrollTop);
      document.removeEventListener("focusin", forceScrollTop);
    };
  }, []);

  // ─── Fetch pages from DB ──────────────────────────────────────────────────
  const fetchPages = useCallback(async () => {
    if (isMockUser) return;
    try {
      const res = await fetch('/api/pages');
      if (!res.ok) throw new Error('Failed to fetch pages');
      const data = await res.json();
      const items: PageItem[] = data.map(dbRowToPageItem);
      setPages(items);
      if (items.length > 0 && !items.find(p => p.id === activePageId)) {
        setActivePageId(items[0].id);
      }
    } catch (err) {
      console.error('Error fetching pages:', err);
      toast.error('Failed to load pages');
    } finally {
      setIsLoading(false);
    }
  }, [isMockUser]);

  // ─── Initial fetch on mount ────────────────────────────────────────────────
  useEffect(() => {
    if (isMockUser) {
      // Offline dev mode — use hardcoded pages so the UI still works
      setPages([
        { id: '1', title: 'Lecture 1', content: '', parentId: null, isOpen: true },
        { id: '2', title: 'Semantic Web', content: '', parentId: '1' },
        { id: '3', title: 'College Marital', content: '', parentId: null },
      ]);
      setActivePageId('1');
      setIsLoading(false);
      return;
    }

    fetchPages();
  }, [isMockUser, fetchPages]);

  // ─── Debounced PATCH for content updates ───────────────────────────────────
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const persistUpdate = useCallback((id: string, updates: Partial<PageItem>) => {
    if (isMockUser) return;

    // Clear any pending save for this page
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);

    saveTimerRef.current = setTimeout(async () => {
      try {
        await fetch('/api/pages', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, ...updates }),
        });
      } catch (err) {
        console.error('Error saving page:', err);
      }
    }, 500); // 500ms debounce
  }, [isMockUser]);

  // ─── Duplicate Page ────────────────────────────────────────────────────────
  const duplicatePage = (id: string) => {
    const pageToDuplicate = pages.find(p => p.id === id);
    if (!pageToDuplicate) return;
    const newId = uuidv4();
    const newPage: PageItem = {
      ...pageToDuplicate,
      id: newId,
      title: `${pageToDuplicate.title} (Copy)`,
    };
    setPages(prev => [...prev, newPage]);
    setActivePageId(newPage.id);

    // Persist to DB
    if (!isMockUser) {
      fetch('/api/pages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPage),
      }).catch(err => console.error('Error duplicating page:', err));
    }
  };

  // ─── Delete Page ───────────────────────────────────────────────────────────
  const deletePage = (id: string) => {
    const getIdsToDelete = (pageId: string, currentPages: PageItem[]): string[] => {
      const children = currentPages.filter(p => p.parentId === pageId).map(p => p.id);
      return [pageId, ...children.flatMap(c => getIdsToDelete(c, currentPages))];
    };
    const idsToDelete = getIdsToDelete(id, pages);
    const newPages = pages.filter(p => !idsToDelete.includes(p.id));
    
    // Clean up references to deleted pages in the content of remaining pages
    const cleanedPages = newPages.map(p => {
      if (!p.content) return p;
      try {
        const parser = new DOMParser();
        const doc = parser.parseFromString(p.content, 'text/html');
        let modified = false;
        
        idsToDelete.forEach(deletedId => {
          const nodes = doc.querySelectorAll(`div[data-page-id="${deletedId}"], div[pageid="${deletedId}"]`);
          if (nodes.length > 0) {
            nodes.forEach(node => node.remove());
            modified = true;
          }
        });
        
        if (modified) {
          return { ...p, content: doc.body.innerHTML };
        }
      } catch (err) {
        console.error("Error parsing content during page deletion:", err);
      }
      return p;
    });

    setPages(cleanedPages);
    if (idsToDelete.includes(activePageId)) {
      setActivePageId(cleanedPages[0]?.id || '');
    }

    // Persist to DB — only delete the root page, CASCADE handles children
    if (!isMockUser) {
      fetch(`/api/pages?id=${id}`, { method: 'DELETE' })
        .catch(err => console.error('Error deleting page:', err));
    }
  };

  // ─── Add Page ──────────────────────────────────────────────────────────────
  const addPage = (parentId: string | null, preventSwitch = false) => {
    const newPage: PageItem = {
      id: uuidv4(),
      title: 'Untitled',
      content: '',
      parentId,
      isOpen: true,
    };
    
    if (parentId) {
      setPages(prev => {
        const updatedPages = prev.map(p => {
          if (p.id === parentId) {
            let updatedContent = p.content;
            if (!preventSwitch) {
              // Add from sidebar: append to content
              updatedContent = (p.content || '') + `<div data-type="page-link" data-page-id="${newPage.id}"></div><p></p>`;
            }
            return { ...p, isOpen: true, content: updatedContent };
          }
          return p;
        });
        return [...updatedPages, newPage];
      });

      // Also persist the parent update
      if (!isMockUser && !preventSwitch) {
        const parentPage = pages.find(p => p.id === parentId);
        if (parentPage) {
          const updatedContent = (parentPage.content || '') + `<div data-type="page-link" data-page-id="${newPage.id}"></div><p></p>`;
          persistUpdate(parentId, { content: updatedContent, isOpen: true });
        }
      }
    } else {
      setPages(prev => [...prev, newPage]);
    }
    if (!preventSwitch) {
      setActivePageId(newPage.id);
      setActiveView("page");
      router.push("/dashboard");
    }

    // Persist new page to DB
    if (!isMockUser) {
      fetch('/api/pages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPage),
      }).catch(err => console.error('Error adding page:', err));
    }

    return newPage.id;
  };

  // ─── Update Page ───────────────────────────────────────────────────────────
  const updatePage = (id: string, updates: Partial<PageItem>) => {
    setPages(prev => prev.map(p => p.id === id ? { ...p, ...updates } : p));
    persistUpdate(id, updates);
  };

  const activePage = pages.find(p => p.id === activePageId);
  const selectPage = (id: string) => {
    setActivePageId(id);
    setActiveView("page");
    router.push("/dashboard");
  };

  const router = useRouter();

  const handleLogout = async () => {
    const result = await authService.logout();
    if (result.success) {
      toast.success(result.message);
      router.push("/auth/login");
    } else {
      toast.error(result.message);
    }
  };

  const displayName =
    user.user_metadata?.full_name ||
    user.user_metadata?.name ||
    user.email ||
    "User";

  return (
<div className='h-screen w-full flex bg-black relative overflow-hidden'>
      <div className="absolute top-[-25%] left-[-30%] w-[70vw] max-w-[1300px] h-[600px] bg-primary/30 blur-[210px] rounded-full z-0 pointer-events-none"></div>
      <div className="absolute bottom-[-35%] right-[-45%] w-[70vw] max-w-[1300px] h-[600px] bg-primary/20 blur-[210px] rounded-full z-0 pointer-events-none"></div>
      <Sidebar 
        pages={pages}
        activePageId={activePageId}
        activeView={activeView}
        onSelectPage={selectPage}
        onSelectHome={() => {
          setActiveView("home");
          router.push("/dashboard");
        }}
        onOpenSearch={() => setIsSearchOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onAddPage={addPage}
        onTogglePage={(id) => updatePage(id, { isOpen: !pages.find(p => p.id === id)?.isOpen })}
        onDeletePage={deletePage}
        user={user}
        onLogout={handleLogout}
      />
      {activeView === "home" && (
        <DashboardHome
          displayName={displayName}
          pages={pages}
          onOpenSearch={() => setIsSearchOpen(true)}
          onSelectPage={selectPage}
        />
      )}
      {activeView === "page" && (
        <ContentEditor 
          activePage={activePage}
          allPages={pages}
          updatePage={updatePage}
          onSelectPage={selectPage}
          onDuplicatePage={duplicatePage}
          onDeletePage={deletePage}
          onAddPage={addPage}
        />
      )}
      {activeView === "trash" && (
        <DashboardTrash pages={pages} isMockUser={isMockUser} onPagesChanged={fetchPages} />
      )}
      {activeView === "page" && (
        <AIPanel 
          user={user} 
          activePageId={activePageId} 
          activePageContent={activePage?.content}
          onUpdatePage={updatePage}
        />
      )}
      <SearchOverlay
        isOpen={isSearchOpen}
        pages={pages}
        onClose={() => setIsSearchOpen(false)}
        onSelectPage={selectPage}
      />
      <DashboardSettings
        isOpen={isSettingsOpen}
        onClose={() => {
          setIsSettingsOpen(false);
          if (window.location.pathname.endsWith("/settings")) {
            router.push("/dashboard");
          }
        }}
        displayName={displayName}
        email={user.email}
      />
      <Toaster theme="dark" position="bottom-right" />
    </div>

  );
}
