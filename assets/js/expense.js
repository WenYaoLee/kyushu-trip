import { initializeApp } from "https://www.gstatic.com/firebasejs/12.0.0/firebase-app.js";
import { firebaseConfig } from "./firebase-config.js";
        import {
            getFirestore,
            collection,
            addDoc,
            updateDoc,
            doc,
            onSnapshot,
            query,
            orderBy,
            serverTimestamp
        } from "https://www.gstatic.com/firebasejs/12.0.0/firebase-firestore.js";
        import {
            getAuth,
            GoogleAuthProvider,
            signInWithPopup,
            signOut,
            onAuthStateChanged
        } from "https://www.gstatic.com/firebasejs/12.0.0/firebase-auth.js";

        const app = initializeApp(firebaseConfig);
        const db = getFirestore(app);
        const auth = getAuth(app);
        const provider = new GoogleAuthProvider();
        const expenseRef = collection(db, "expenses");

        const members = ["文耀", "欣儀", "建泓", "建甫", "馥伃"];

        // 這裡請改成你允許記帳的 Google Email
        const allowUsers = [
            "s0980642866@gmail.com",
            "monkey7118038@gmail.com",
            "karen08110811@gmail.com",
            "seered086@gmail.com",
            "aken860711@gmail.com"
        ];

        const $ = (id) => document.getElementById(id);
        const yen = (num) => "¥" + Math.round(Number(num || 0)).toLocaleString("ja-JP");

        function setStatus(message) {
            const el = $("expenseStatus");
            if (el) el.textContent = message;
        }

        function escapeHtml(str) {
            return String(str ?? "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function isAllowedUser(user) {
            return !!user && allowUsers.includes(user.email);
        }

        function formatTripDate(value) {
            if (!value) return "";
            return String(value).replace("T", " ");
        }

        function getDateOnly(value) {
            if (!value) return "未分類";
            return String(value).substring(0, 10);
        }

        function formatTimestamp(ts) {
            if (!ts || !ts.toDate) return "";
            const d = ts.toDate();
            const pad = (n) => String(n).padStart(2, "0");
            return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
        }

        function getCheckedMembers() {
            return Array.from(document.querySelectorAll(".expense-member:checked"))
                .map(x => x.value);
        }

        async function googleLogin() {
            try {
                await signInWithPopup(auth, provider);
            } catch (err) {
                console.error(err);
                alert("Google 登入失敗：" + err.message);
            }
        }

        async function googleLogout() {
            try {
                await signOut(auth);
            } catch (err) {
                console.error(err);
                alert("登出失敗：" + err.message);
            }
        }

        function updateAuthUI(user) {
            const loginBtn = $("googleLoginBtn");
            const logoutBtn = $("googleLogoutBtn");
            const loginUser = $("loginUser");
            const authHint = $("authHint");
            const addBtn = $("addExpenseBtn");
            const deleteBtns = document.querySelectorAll(".expense-delete-btn");

            if (!user) {
                if (loginBtn) loginBtn.style.display = "inline-block";
                if (logoutBtn) logoutBtn.style.display = "none";
                if (loginUser) loginUser.textContent = "尚未登入";
                if (authHint) {
                    authHint.textContent = "登入 Google 後才能新增或刪除支出。";
                    authHint.classList.remove("auth-denied");
                }
                if (addBtn) addBtn.disabled = true;
                deleteBtns.forEach(btn => btn.disabled = true);
                return;
            }

            const allowed = isAllowedUser(user);

            if (loginBtn) loginBtn.style.display = "none";
            if (logoutBtn) logoutBtn.style.display = "inline-block";
            if (loginUser) loginUser.textContent = `👤 ${user.displayName || user.email}`;

            if (allowed) {
                if (authHint) {
                    authHint.textContent = `已登入：${user.email}，可以新增與刪除支出。`;
                    authHint.classList.remove("auth-denied");
                }
                if (addBtn) addBtn.disabled = false;
                deleteBtns.forEach(btn => btn.disabled = false);
            } else {
                if (authHint) {
                    authHint.textContent = `此帳號未授權記帳：${user.email}`;
                    authHint.classList.add("auth-denied");
                }
                if (addBtn) addBtn.disabled = true;
                deleteBtns.forEach(btn => btn.disabled = true);
            }
        }

        async function addExpense() {
            const user = auth.currentUser;

            if (!user) {
                alert("請先登入 Google");
                return;
            }

            if (!isAllowedUser(user)) {
                alert("這個 Google 帳號沒有記帳權限");
                return;
            }

            const tripDate = $("expenseTripDate")?.value || "";
            const category = $("expenseCategory")?.value || "";
            const title = $("expenseTitle")?.value.trim() || "";
            const amount = Number($("expenseAmount")?.value || 0);
            const payer = $("expensePayer")?.value || "";
            const splitMembers = getCheckedMembers();
            const note = $("expenseNote")?.value.trim() || "";

            if (!tripDate || !title || !amount || amount <= 0 || splitMembers.length === 0) {
                alert("請確認日期、項目、金額與分攤成員都有填寫");
                return;
            }

            const btn = $("addExpenseBtn");
            if (btn) {
                btn.disabled = true;
                btn.textContent = "新增中...";
            }

            try {
                await addDoc(expenseRef, {
                    tripDate,
                    category,
                    title,
                    amount,
                    payer,
                    members: splitMembers,
                    note,
                    Status: "Y",
                    deletedAt: null,
                    CreatedBy: user.email,
                    CreatedName: user.displayName || "",
                    createdAt: serverTimestamp(),
                    updatedAt: serverTimestamp()
                });

                $("expenseTitle").value = "";
                $("expenseAmount").value = "";
                $("expenseNote").value = "";
                setStatus("新增成功，已同步到 Firebase");
            } catch (err) {
                console.error(err);
                alert("新增失敗：" + err.message);
                setStatus("新增失敗，請檢查 Firebase 規則或網路連線");
            } finally {
                if (btn) {
                    btn.disabled = !isAllowedUser(auth.currentUser);
                    btn.textContent = "新增支出";
                }
            }
        }

        async function deleteExpense(id, createdBy) {
            const user = auth.currentUser;

            if (!user) {
                alert("請先登入 Google");
                return;
            }

            if (!isAllowedUser(user)) {
                alert("這個 Google 帳號沒有刪除權限");
                return;
            }

            if (createdBy !== user.email) {
                alert("只能刪除自己新增的支出");
                return;
            }

            if (!confirm("確定要刪除這筆支出嗎？")) return;

            try {
                await updateDoc(doc(db, "expenses", id), {
                    Status: "N",
                    deletedAt: serverTimestamp(),
                    DeletedBy: user.email,
                    DeletedName: user.displayName || "",
                    updatedAt: serverTimestamp()
                });

                setStatus("已將支出標記為刪除");
            } catch (err) {
                console.error(err);
                alert("刪除失敗：" + err.message);
            }
        }

        function renderExpenses(expenses) {
            const list = $("expenseList");
            if (!list) {
                console.error("找不到 expenseList，請確認支出明細區塊 ID 是否正確");
                return;
            }

            if (!expenses.length) {
                list.innerHTML = `<div class="expense-empty">尚未新增支出</div>`;
                return;
            }

            const grouped = {};
            expenses.forEach(exp => {
                const date = getDateOnly(exp.tripDate);
                if (!grouped[date]) grouped[date] = [];
                grouped[date].push(exp);
            });

            const sortedDates = Object.keys(grouped).sort();

            list.innerHTML = sortedDates.map(date => {
                const items = grouped[date].sort((a, b) => String(a.tripDate || "").localeCompare(String(b.tripDate || "")));
                const total = items.reduce((sum, x) => sum + Number(x.amount || 0), 0);

                return `
                        <details class="expense-day-card">
                            <summary>
                                <div class="expense-day-header">
                                    <div>
                                        <div class="expense-day-title">📅 ${escapeHtml(date)}</div>
                                        <div class="expense-day-count">共 ${items.length} 筆</div>
                                    </div>
                                    <div class="expense-day-total">${yen(total)}</div>
                                </div>
                            </summary>

                            <div class="expense-day-body">
                                ${items.map(exp => {
                    const memberText = Array.isArray(exp.members) ? exp.members.join("、") : "";
                    const createdText = formatTimestamp(exp.createdAt);
                    const createdBy = exp.CreatedName || exp.CreatedBy || "";

                    return `
                                        <div class="expense-item">
                                            <div class="expense-item-head">
                                                <div>
                                                    <div class="expense-item-title">${escapeHtml(exp.title)}</div>
                                                    <div class="expense-item-meta">
                                                        ${escapeHtml(formatTripDate(exp.tripDate))} · ${escapeHtml(exp.category)}
                                                    </div>
                                                </div>
                                                <div class="expense-item-amount">${yen(exp.amount)}</div>
                                            </div>

                                            <div class="expense-item-meta">付款人：${escapeHtml(exp.payer)}</div>
                                            <div class="expense-item-meta">分攤：${escapeHtml(memberText)}</div>

                                            ${exp.note ? `<div class="expense-item-note">${escapeHtml(exp.note)}</div>` : ""}
                                            ${createdText ? `<div class="expense-item-meta">建立時間：${escapeHtml(createdText)}</div>` : ""}
                                            ${createdBy ? `<div class="expense-item-meta">建立者：${escapeHtml(createdBy)}</div>` : ""}

                                            <button type="button"
                                                    class="expense-delete-btn"
                                                    data-id="${escapeHtml(exp.id)}"
                                                    data-created-by="${escapeHtml(exp.CreatedBy || "")}">
                                                刪除
                                            </button>
                                        </div>
                                    `;
                }).join("")}
                            </div>
                        </details>
                    `;
            }).join("");

            list.querySelectorAll(".expense-delete-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    deleteExpense(btn.dataset.id, btn.dataset.createdBy);
                });
            });

            updateAuthUI(auth.currentUser);
        }

        function renderSummary(expenses) {
            const total = expenses.reduce((sum, x) => sum + Number(x.amount || 0), 0);
            const average = members.length ? total / members.length : 0;

            if ($("expenseTotal")) $("expenseTotal").textContent = yen(total);
            if ($("expensePeopleCount")) $("expensePeopleCount").textContent = members.length + " 人";
            if ($("expenseAverage")) $("expenseAverage").textContent = yen(average);

            const paid = {};
            const shouldPay = {};

            members.forEach(m => {
                paid[m] = 0;
                shouldPay[m] = 0;
            });

            expenses.forEach(x => {
                const amount = Number(x.amount || 0);
                const payer = x.payer;
                const split = Array.isArray(x.members) && x.members.length ? x.members : members;

                if (paid[payer] === undefined) paid[payer] = 0;
                paid[payer] += amount;

                const each = amount / split.length;

                split.forEach(m => {
                    if (shouldPay[m] === undefined) shouldPay[m] = 0;
                    shouldPay[m] += each;
                });
            });

            const creditors = [];
            const debtors = [];

            members.forEach(m => {
                const balance = paid[m] - shouldPay[m];

                if (balance > 1) {
                    creditors.push({ name: m, amount: balance });
                } else if (balance < -1) {
                    debtors.push({ name: m, amount: -balance });
                }
            });

            creditors.sort((a, b) => b.amount - a.amount);
            debtors.sort((a, b) => b.amount - a.amount);

            const settlements = [];
            let i = 0;
            let j = 0;

            while (i < debtors.length && j < creditors.length) {
                const payAmount = Math.min(debtors[i].amount, creditors[j].amount);

                if (payAmount > 1) {
                    settlements.push({
                        from: debtors[i].name,
                        to: creditors[j].name,
                        amount: payAmount
                    });
                }

                debtors[i].amount -= payAmount;
                creditors[j].amount -= payAmount;

                if (debtors[i].amount <= 1) i++;
                if (creditors[j].amount <= 1) j++;
            }

            const table = $("memberSummaryTable");
            if (!table) return;

            if (settlements.length === 0) {
                table.innerHTML = `
                        <tr>
                            <td colspan="2" style="text-align:center;color:#7a9a7a;">
                                目前沒有需要結算的金額
                            </td>
                        </tr>
                    `;
                return;
            }

            table.innerHTML = settlements.map(x => `
                    <tr>
                        <td>${escapeHtml(x.from)} → ${escapeHtml(x.to)}</td>
                        <td style="color:#d60000;font-weight:800;">${yen(x.amount)}</td>
                    </tr>
                `).join("");
        }

        function startExpenseSync() {
            const q = query(expenseRef, orderBy("tripDate", "asc"));

            onSnapshot(q, snapshot => {
                const expenses = snapshot.docs
                    .map(d => ({
                        id: d.id,
                        ...d.data()
                    }))
                    .filter(x => x.Status !== "N");

                renderExpenses(expenses);
                renderSummary(expenses);
                setStatus(`Firebase 已同步，共 ${expenses.length} 筆支出`);
            }, err => {
                console.error(err);
                setStatus("Firebase 同步失敗：" + err.message);
            });
        }

        export function initExpenseView() {
            const dateInput = $("expenseTripDate");
            if (dateInput && !dateInput.value) {
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                dateInput.value = now.toISOString().slice(0, 16);
            }

            const loginBtn = $("googleLoginBtn");
            const logoutBtn = $("googleLogoutBtn");
            const addBtn = $("addExpenseBtn");

            if (loginBtn) loginBtn.addEventListener("click", googleLogin);
            if (logoutBtn) logoutBtn.addEventListener("click", googleLogout);

            if (!addBtn) {
                console.error("找不到 addExpenseBtn，新增支出按鈕沒有綁定成功");
            } else {
                addBtn.disabled = true;
                addBtn.addEventListener("click", addExpense);
            }

            onAuthStateChanged(auth, user => {
                updateAuthUI(user);
            });                            

            startExpenseSync();
        }
